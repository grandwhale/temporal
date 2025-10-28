# $AIRFLOW_HOME/plugins/custom_variable_view.py
from airflow.providers.fab.www.views import VariableModelView
from flask import flash, redirect
from flask_appbuilder import expose
from flask_login import current_user
from werkzeug.exceptions import Forbidden
import logging

log = logging.getLogger(__name__)

class CustomVariableModelView(VariableModelView):
    """
    팀 프리픽스 기반 변수 접근 제어를 위한 커스텀 뷰
    """
    
    TEAM_ROLE_SUFFIX = '-user'
    
    def _get_user_team_prefixes(self):
        """사용자의 팀 프리픽스 목록 반환"""
        if not current_user or not current_user.is_authenticated:
            return []
        
        team_prefixes = []
        for role in current_user.roles:
            # Admin은 모든 접근 허용
            if role.name == 'Admin':
                return ['*']
            
            # 팀 롤 패턴 체크 (예: fdc-user, eds-user)
            if role.name.endswith(self.TEAM_ROLE_SUFFIX):
                prefix = role.name.replace(self.TEAM_ROLE_SUFFIX, '')
                team_prefixes.append(prefix)
        
        return team_prefixes
    
    def _can_access_variable(self, var_key):
        """변수에 접근 가능한지 체크"""
        team_prefixes = self._get_user_team_prefixes()
        
        # Admin이거나 팀 롤이 없으면 기본 권한 체크로 처리
        if not team_prefixes or '*' in team_prefixes:
            return True
        
        # 변수명이 팀 프리픽스로 시작하는지 체크
        for prefix in team_prefixes:
            if var_key.startswith(f"{prefix}-"):
                log.info(
                    f"User {current_user.username} can access variable '{var_key}' "
                    f"via team role '{prefix}{self.TEAM_ROLE_SUFFIX}'"
                )
                return True
        
        return False
    
    def _check_and_flash_error(self, var_key):
        """권한 체크 후 에러 메시지 표시"""
        if not self._can_access_variable(var_key):
            team_prefixes = self._get_user_team_prefixes()
            flash(
                f"You can only manage variables starting with: "
                f"{', '.join([f'{p}-' for p in team_prefixes])}. "
                f"Variable '{var_key}' is not allowed.",
                "danger"
            )
            return False
        return True
    
    def pre_add(self, item):
        """변수 생성 전 호출"""
        if not self._check_and_flash_error(item.key):
            raise Forbidden(
                f"Access denied: You cannot create variable '{item.key}'"
            )
    
    def pre_update(self, item):
        """변수 수정 전 호출"""
        if not self._check_and_flash_error(item.key):
            raise Forbidden(
                f"Access denied: You cannot modify variable '{item.key}'"
            )
    
    def pre_delete(self, item):
        """변수 삭제 전 호출"""
        if not self._check_and_flash_error(item.key):
            raise Forbidden(
                f"Access denied: You cannot delete variable '{item.key}'"
            )
