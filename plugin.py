# plugins/team_variable_auth.py
"""
Airflow 3.0.6용 팀 프리픽스 기반 변수 권한 제어

요구사항:
- fdc-user 롤: fdc-로 시작하는 변수만 생성/수정/삭제
- eds-user 롤: eds-로 시작하는 변수만 생성/수정/삭제
- 한 사용자가 여러 팀 롤 동시 소유 가능
"""

from airflow.plugins_manager import AirflowPlugin
from airflow.providers.fab.auth_manager.security_manager.override import (
    FabAirflowSecurityManagerOverride
)
from flask import g
from typing import List, Optional
import logging

log = logging.getLogger(__name__)

# 팀별 프리픽스 매핑
TEAM_PREFIX_MAP = {
    'fdc-user': 'fdc-',
    'eds-user': 'eds-',
}

class TeamVariableSecurityManager(FabAirflowSecurityManagerOverride):
    """팀 프리픽스 기반 변수 권한 제어"""
    
    def get_user_team_prefixes(self, user) -> List[str]:
        """
        사용자의 모든 팀 프리픽스 반환
        한 사용자가 여러 팀에 속할 수 있음
        """
        if not user or not hasattr(user, 'roles'):
            return []
        
        prefixes = []
        for role in user.roles:
            if role.name in TEAM_PREFIX_MAP:
                prefix = TEAM_PREFIX_MAP[role.name]
                if prefix not in prefixes:
                    prefixes.append(prefix)
        
        return prefixes
    
    def is_admin_user(self, user) -> bool:
        """Admin 권한 확인"""
        if not user or not hasattr(user, 'roles'):
            return False
        return any(role.name == 'Admin' for role in user.roles)
    
    def is_authorized_variable(
        self,
        method: str,
        variable_key: Optional[str] = None,
        user = None
    ) -> bool:
        """
        핵심 권한 체크 메서드 - Airflow가 자동으로 호출함
        
        Args:
            method: 'GET', 'POST', 'PUT', 'DELETE'
            variable_key: 변수 키 (예: 'fdc-api-key')
            user: 사용자 객체
        """
        # 사용자 가져오기
        if user is None:
            try:
                user = g.user
            except (RuntimeError, AttributeError):
                log.warning("Cannot get user from Flask context")
                return False
        
        # 1단계: 기본 FAB 권한 체크 (can_create, can_edit 등)
        has_basic_permission = super().is_authorized_variable(
            method, variable_key, user
        )
        
        if not has_basic_permission:
            return False
        
        # 2단계: Admin은 모든 변수 접근 가능
        if self.is_admin_user(user):
            return True
        
        # 3단계: 변수 키가 없으면 (목록 조회) 기본 권한만 체크
        if variable_key is None:
            return True  # get_authorized_variables에서 필터링
        
        # 4단계: 팀 프리픽스 기반 권한 체크
        user_prefixes = self.get_user_team_prefixes(user)
        
        if not user_prefixes:
            log.warning(f"User {user.username} has no team roles")
            return False
        
        # 변수 키가 사용자 팀 프리픽스로 시작하는지 확인
        has_access = any(
            variable_key.startswith(prefix) 
            for prefix in user_prefixes
        )
        
        if not has_access:
            log.warning(
                f"Access denied: {user.username} tried to access '{variable_key}'"
            )
        
        return has_access
    
    def get_authorized_variables(self, methods, user=None):
        """
        UI 변수 목록 조회 시 필터링
        팀 프리픽스에 해당하는 변수만 반환
        """
        if user is None:
            try:
                user = g.user
            except (RuntimeError, AttributeError):
                return []
        
        # Admin은 모든 변수 조회
        if self.is_admin_user(user):
            return super().get_authorized_variables(methods, user)
        
        # 모든 변수 가져오기
        all_variables = super().get_authorized_variables(methods, user)
        
        # 팀 프리픽스 필터링
        user_prefixes = self.get_user_team_prefixes(user)
        
        if not user_prefixes:
            return []
        
        filtered = [
            var for var in all_variables
            if any(var.key.startswith(prefix) for prefix in user_prefixes)
        ]
        
        log.info(
            f"User {user.username}: {len(filtered)}/{len(all_variables)} variables"
        )
        
        return filtered


class TeamVariableAuthPlugin(AirflowPlugin):
    """Airflow 플러그인 등록 (메타데이터용)"""
    name = "team_variable_auth"
