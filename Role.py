맞습니다! 제가 놓친 부분이 있네요. 여러 팀에 동시에 속할 수 있고, 각 팀별로 해당 프리픽스 변수만 관리할 수 있어야 합니다. 수정된 코드를 제공하겠습니다.

## 개선된 구현 방법

### 1. 커스텀 시큐리티 매니저 (webserver_config.py)

```python
from airflow.providers.fab.auth_manager.security_manager.override import FabAirflowSecurityManagerOverride
from flask import request
import logging

log = logging.getLogger(__name__)

class CustomSecurityManager(FabAirflowSecurityManagerOverride):
    """
    팀별 롤을 가진 사용자가 해당 팀 프리픽스 변수만 관리하도록 제한
    예: fdc-user 롤 -> fdc-* 변수만, eds-user 롤 -> eds-* 변수만
    """
    
    # 팀 롤 패턴 정의 (롤 이름에서 팀 프리픽스 추출)
    TEAM_ROLE_SUFFIX = '-user'
    
    def has_access(self, permission_name, resource_name, user=None):
        """권한 체크 오버라이드"""
        from flask_login import current_user
        
        if user is None:
            user = current_user
        
        # Variables 리소스에 대한 변경 작업인 경우
        if resource_name == 'Variables' and permission_name in ['can_create', 'can_edit', 'can_delete']:
            team_roles = self._get_user_team_roles(user)
            
            # 팀 롤이 하나라도 있는 경우에만 체크
            if team_roles:
                var_key = self._extract_variable_key_from_request()
                
                if var_key:
                    # 사용자가 이 변수에 접근할 수 있는지 체크
                    if not self._can_access_variable(var_key, team_roles, user):
                        log.warning(
                            f"User {user.username} with roles {[r.name for r in user.roles]} "
                            f"attempted to {permission_name} variable '{var_key}' "
                            f"without proper team prefix"
                        )
                        return False
        
        # 기본 권한 체크로 위임
        return super().has_access(permission_name, resource_name, user)
    
    def _get_user_team_roles(self, user):
        """
        사용자의 팀 롤 목록 추출
        예: 'fdc-user', 'eds-user' 롤이 있으면 ['fdc', 'eds'] 반환
        """
        if not user:
            return []
        
        team_prefixes = []
        for role in user.roles:
            # Admin 롤은 모든 변수 접근 가능
            if role.name == 'Admin':
                return ['*']  # 와일드카드로 모든 접근 허용
            
            # 팀 롤 패턴 체크 (예: fdc-user, eds-user)
            if role.name.endswith(self.TEAM_ROLE_SUFFIX):
                prefix = role.name.replace(self.TEAM_ROLE_SUFFIX, '')
                team_prefixes.append(prefix)
        
        return team_prefixes
    
    def _can_access_variable(self, var_key, team_roles, user):
        """
        사용자가 해당 변수에 접근할 수 있는지 체크
```
