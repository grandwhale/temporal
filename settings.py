# $AIRFLOW_HOME/dags/airflow_local_settings.py
import os
from airflow.models import DAG

def dag_policy(dag: DAG):
    """모든 DAG에 자동으로 적용되는 정책"""
    
    # DAG 파일 경로에서 팀 폴더 추출
    if dag.fileloc:
        path_parts = dag.fileloc.split('/')
        
        if 'dags' in path_parts:
            dags_index = path_parts.index('dags')
            if len(path_parts) > dags_index + 1:
                team_folder = path_parts[dags_index + 1]
                
                # 팀 폴더명이 실제 폴더인 경우 (파일명이 아닌)
                if team_folder and team_folder.endswith('.py') is False:
                    role_name = f"{team_folder}-user"
                    
                    # 기존 access_control과 병합
                    if dag.access_control is None:
                        dag.access_control = {}
                    
                    dag.access_control[role_name] = {'can_read', 'can_edit'}
