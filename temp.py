import os
from airflow.www.security import AirflowSecurityManager
from flask_appbuilder.security.sqla.models import Role

class CustomSecurityManager(AirflowSecurityManager):
    
    def sync_roles(self):
        """
        역할 자동 생성 및 동기화
        """
        super().sync_roles()
        
        # DAG 폴더 구조 기반으로 역할 생성
        team_folders = ['fdc', 'marketing', 'finance']
        
        for team in team_folders:
            role_name = f"{team}-user"
            
            # 역할이 없으면 생성
            role = self.find_role(role_name)
            if not role:
                role = self.add_role(role_name)
            
            # 기본 권한 부여
            self._grant_basic_permissions(role)
    
    def _grant_basic_permissions(self, role):
        """기본 UI 접근 권한 부여"""
        basic_perms = [
            ('can_read', 'Website'),
            ('menu_access', 'Browse Menu'),
            ('menu_access', 'DAG Runs'),
            ('menu_access', 'Task Instances'),
            ('can_read', 'Dag Code'),
            ('can_read', 'Task Instances'),
            ('can_read', 'Task Logs'),
            ('can_read', 'Dag Runs'),
            ('can_create', 'Dag Runs'),
            ('can_edit', 'Dag Runs'),
        ]
        
        for action, resource in basic_perms:
            perm = self.find_permission_view_menu(action, resource)
            if perm and perm not in role.permissions:
                role.permissions.append(perm)
        
        self.get_session.commit()
    
    def sync_perm_for_dag(self, dag_id, access_control=None):
        """
        DAG 권한을 폴더 기반으로 자동 할당
        """
        from airflow.models import DagBag
        
        # DAG 파일 경로 확인
        dag_bag = DagBag()
        if dag_id in dag_bag.dags:
            dag = dag_bag.dags[dag_id]
            dag_file = dag.fileloc
            
            # 폴더명에서 팀 추출
            # 예: /home/airflow/dags/fdc/pipeline.py -> 'fdc'
            dags_folder = self.appbuilder.app.config.get('DAGS_FOLDER', '')
            relative_path = os.path.relpath(dag_file, dags_folder)
            team_folder = relative_path.split(os.sep)[0]
            
            # dags 직속 파일이 아닌 경우에만 팀별 권한 부여
            if team_folder and team_folder != os.path.basename(dag_file):
                role_name = f"{team_folder}-user"
                role = self.find_role(role_name)
                
                if role:
                    # DAG별 권한 자동 부여
                    self._grant_dag_permissions(role, dag_id)
        
        # 기존 access_control이 있으면 그것도 적용
        if access_control:
            super().sync_perm_for_dag(dag_id, access_control)
        else:
            super().sync_perm_for_dag(dag_id, None)
    
    def _grant_dag_permissions(self, role, dag_id):
        """특정 역할에 DAG 권한 부여"""
        dag_perms = [
            ('can_read', f'DAG:{dag_id}'),
            ('can_edit', f'DAG:{dag_id}'),
        ]
        
        for action, resource in dag_perms:
            perm = self.find_permission_view_menu(action, resource)
            if perm and perm not in role.permissions:
                role.permissions.append(perm)
        
        self.get_session.commit()

SECURITY_MANAGER_CLASS = CustomSecurityManager
