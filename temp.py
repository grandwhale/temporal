# ~/airflow/webserver_config.py
import os
import logging
from pathlib import Path
from airflow.providers.fab.auth_manager.security_manager.override import (
    FabAirflowSecurityManagerOverride
)
from airflow.security import permissions
from flask_appbuilder.security.sqla.models import Role

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


class FolderBasedSecurityManager(FabAirflowSecurityManagerOverride):
    """
    폴더 기반으로 DAG 권한을 자동 할당하는 커스텀 Security Manager
    """
    
    # 팀별 설정 (팀명과 역할 매핑)
    TEAM_CONFIGS = {
        'fdc': {
            'role_name': 'fdc-user',
            'description': 'FDC team role'
        },
        'marketing': {
            'role_name': 'marketing-user',
            'description': 'Marketing team role'
        },
        'finance': {
            'role_name': 'finance-user',
            'description': 'Finance team role'
        }
    }
    
    def __init__(self, appbuilder):
        super().__init__(appbuilder)
        self._ensure_team_roles_exist()
    
    def _ensure_team_roles_exist(self):
        """
        팀 역할이 DB에 존재하는지 확인하고 없으면 생성
        """
        for team_name, config in self.TEAM_CONFIGS.items():
            role_name = config['role_name']
            role = self.find_role(role_name)
            
            if not role:
                log.info(f"Creating team role: {role_name}")
                role = self.add_role(role_name)
                
                # 기본 UI 접근 권한 부여
                self._grant_basic_ui_permissions(role)
    
    def _grant_basic_ui_permissions(self, role):
        """
        역할에 기본 UI 접근 권한 부여
        (전체 DAGs 권한은 제외)
        """
        basic_permissions = [
            # Website 접근
            (permissions.ACTION_CAN_READ, permissions.RESOURCE_WEBSITE),
            
            # 메뉴 접근
            (permissions.ACTION_CAN_ACCESS_MENU, permissions.RESOURCE_BROWSE_MENU),
            (permissions.ACTION_CAN_ACCESS_MENU, permissions.RESOURCE_DAG),
            (permissions.ACTION_CAN_ACCESS_MENU, permissions.RESOURCE_DAG_RUN),
            (permissions.ACTION_CAN_ACCESS_MENU, permissions.RESOURCE_TASK_INSTANCE),
            
            # DAG 관련 리소스 (개별 DAG에 대해서만, 전체는 제외)
            (permissions.ACTION_CAN_READ, permissions.RESOURCE_DAG_CODE),
            (permissions.ACTION_CAN_READ, permissions.RESOURCE_DAG_RUN),
            (permissions.ACTION_CAN_READ, permissions.RESOURCE_TASK_INSTANCE),
            (permissions.ACTION_CAN_READ, permissions.RESOURCE_TASK_LOG),
            
            # DAG 실행 권한
            (permissions.ACTION_CAN_CREATE, permissions.RESOURCE_DAG_RUN),
            (permissions.ACTION_CAN_EDIT, permissions.RESOURCE_DAG_RUN),
            (permissions.ACTION_CAN_EDIT, permissions.RESOURCE_TASK_INSTANCE),
            
            # XCom (필요시)
            (permissions.ACTION_CAN_READ, permissions.RESOURCE_XCOM),
            
            # 프로필 관리
            (permissions.ACTION_CAN_READ, permissions.RESOURCE_MY_PASSWORD),
            (permissions.ACTION_CAN_EDIT, permissions.RESOURCE_MY_PASSWORD),
            (permissions.ACTION_CAN_READ, permissions.RESOURCE_MY_PROFILE),
            (permissions.ACTION_CAN_EDIT, permissions.RESOURCE_MY_PROFILE),
        ]
        
        for action, resource_name in basic_permissions:
            perm = self.find_permission_view_menu(action, resource_name)
            if perm and perm not in role.permissions:
                self.add_permission_to_role(role, perm)
        
        self.get_session.commit()
        log.info(f"Granted basic UI permissions to role: {role.name}")
    
    def sync_perm_for_dag(self, dag_id, access_control=None):
        """
        DAG 권한 동기화 - 폴더 기반으로 자동 권한 부여
        """
        # 먼저 부모 클래스의 sync 실행 (access_control 처리)
        super().sync_perm_for_dag(dag_id, access_control)
        
        # access_control이 명시적으로 설정되어 있으면 폴더 기반 자동 할당 스킵
        if access_control is not None:
            log.info(f"DAG {dag_id} has explicit access_control, skipping folder-based assignment")
            return
        
        # DAG 파일 경로 확인
        dag_file_path = self._get_dag_file_path(dag_id)
        if not dag_file_path:
            return
        
        # 폴더명에서 팀 추출
        team_name = self._extract_team_from_path(dag_file_path)
        if not team_name:
            log.debug(f"DAG {dag_id} not in a team folder, skipping auto-permission")
            return
        
        # 팀 역할 찾기
        team_config = self.TEAM_CONFIGS.get(team_name)
        if not team_config:
            log.warning(f"Unknown team folder: {team_name}")
            return
        
        role_name = team_config['role_name']
        role = self.find_role(role_name)
        
        if not role:
            log.warning(f"Role {role_name} not found for team {team_name}")
            return
        
        # DAG 권한 부여
        self._grant_dag_permissions_to_role(role, dag_id)
        log.info(f"Auto-granted permissions for DAG {dag_id} to role {role_name} (team: {team_name})")
    
    def _get_dag_file_path(self, dag_id):
        """
        DAG ID로부터 DAG 파일 경로 가져오기
        """
        try:
            from airflow.models import DagBag, DagModel
            
            # DagModel에서 파일 경로 조회
            dag_model = self.get_session.query(DagModel).filter(
                DagModel.dag_id == dag_id
            ).first()
            
            if dag_model and dag_model.fileloc:
                return dag_model.fileloc
            
            # DagBag에서 조회 (fallback)
            dag_bag = DagBag(read_dags_from_db=False)
            if dag_id in dag_bag.dags:
                return dag_bag.dags[dag_id].fileloc
                
        except Exception as e:
            log.error(f"Error getting DAG file path for {dag_id}: {e}")
        
        return None
    
    def _extract_team_from_path(self, dag_file_path):
        """
        DAG 파일 경로에서 팀 폴더명 추출
        예: /home/airflow/dags/fdc/pipeline.py -> 'fdc'
        """
        try:
            dags_folder = self.appbuilder.app.config.get('DAGS_FOLDER')
            if not dags_folder:
                from airflow.configuration import conf
                dags_folder = conf.get('core', 'dags_folder')
            
            # 상대 경로 계산
            dag_path = Path(dag_file_path)
            dags_path = Path(dags_folder)
            
            try:
                relative_path = dag_path.relative_to(dags_path)
            except ValueError:
                # 경로가 dags_folder 밖에 있는 경우
                return None
            
            # 첫 번째 폴더명 추출
            parts = relative_path.parts
            if len(parts) > 1:  # 서브폴더에 있는 경우만
                team_folder = parts[0]
                # 팀 설정에 있는 폴더인지 확인
                if team_folder in self.TEAM_CONFIGS:
                    return team_folder
            
        except Exception as e:
            log.error(f"Error extracting team from path {dag_file_path}: {e}")
        
        return None
    
    def _grant_dag_permissions_to_role(self, role, dag_id):
        """
        특정 역할에 DAG 권한 부여
        """
        dag_permissions = [
            (permissions.ACTION_CAN_READ, f'{permissions.RESOURCE_DAG_PREFIX}{dag_id}'),
            (permissions.ACTION_CAN_EDIT, f'{permissions.RESOURCE_DAG_PREFIX}{dag_id}'),
        ]
        
        for action, resource_name in dag_permissions:
            perm = self.find_permission_view_menu(action, resource_name)
            if perm:
                if perm not in role.permissions:
                    self.add_permission_to_role(role, perm)
            else:
                # 권한이 없으면 생성
                self.create_permission(action, resource_name)
                perm = self.find_permission_view_menu(action, resource_name)
                if perm:
                    self.add_permission_to_role(role, perm)
        
        self.get_session.commit()


# Security Manager 설정
SECURITY_MANAGER_CLASS = FolderBasedSecurityManager
