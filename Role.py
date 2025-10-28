from airflow.providers.fab.auth_manager.security_manager.override import FabAirflowSecurityManagerOverride
from flask import request
import logging

log = logging.getLogger(__name__)

class CustomSecurityManager(FabAirflowSecurityManagerOverride):
    """
    fdc-user 롤을 가진 사용자가 fdc- 프리픽스 변수만 관리하도록 제한
    """
    
    def has_access(self, permission_name, resource_name, user=None):
        """권한 체크 오버라이드"""
        from flask_login import current_user
        
        if user is None:
            user = current_user
        
        # fdc-user 롤 체크
        if user and self._has_fdc_user_role(user):
            # Variables 리소스에 대한 작업인 경우
            if resource_name == 'Variables':
                if permission_name in ['can_create', 'can_edit', 'can_delete']:
                    # 변수명 체크
                    var_key = self._extract_variable_key_from_request()
                    if var_key and not var_key.startswith('fdc-'):
                        log.warning(
                            f"User {user.username} with fdc-user role attempted to "
                            f"{permission_name} variable '{var_key}' without fdc- prefix"
                        )
                        return False
        
        # 기본 권한 체크로 위임
        return super().has_access(permission_name, resource_name, user)
    
    def _has_fdc_user_role(self, user):
        """사용자가 fdc-user 롤을 가지고 있는지 확인"""
        return any(role.name == 'fdc-user' for role in user.roles)
    
    def _extract_variable_key_from_request(self):
        """HTTP 요청에서 변수명 추출"""
        try:
            # POST/PUT 요청 (생성/수정)
            if request.method in ['POST', 'PUT']:
                # JSON 데이터
                if request.is_json:
                    data = request.get_json()
                    return data.get('key', '')
                # Form 데이터
                else:
                    return request.form.get('key', '')
            
            # DELETE 요청 또는 URL에서 추출
            elif request.method in ['DELETE', 'GET']:
                # URL 파라미터에서 변수명 추출
                # 예: /variable/edit/my_variable_name
                if request.view_args:
                    return request.view_args.get('key', '')
                
                # Query 파라미터에서 추출
                return request.args.get('key', '')
            
        except Exception as e:
            log.error(f"Error extracting variable key: {e}")
            return None
        
        return None

# 커스텀 시큐리티 매니저 적용
SECURITY_MANAGER_CLASS = CustomSecurityManager
