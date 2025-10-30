
# 설정

연결부
```
data:
  # PgBouncer를 사용하지 않을 때
  # metadataConnection:
  #   host: postgresql.database.svc.cluster.local
  #   port: 5432
  
  # PgBouncer를 사용할 때
  metadataSecretName: airflow-db-secret

# Secret 생성 예시
# kubectl create secret generic airflow-db-secret \
#   --from-literal=connection="postgresql://user:pass@airflow-pgbouncer:6543/airflow"
```

예시
```
# values.yaml - 프로덕션 환경
postgresql:
  enabled: false  # 외부 DB 사용

pgbouncer:
  enabled: true
  
  # 연결 수 조정 (Airflow 컴포넌트 수에 따라)
  maxClientConn: 100
  
  # PostgreSQL 연결 풀 크기
  metadataPoolSize: 10
  resultBackendPoolSize: 5
  
  # 인증 타입
  auth_type: scram-sha-256  # PostgreSQL 14+ 권장
  
  # 리소스
  resources:
    limits:
      cpu: "1000m"
      memory: "1Gi"
    requests:
      cpu: "500m"
      memory: "512Mi"
  
  # 로그 레벨
  logLevel: WARNING
  
  # 통계 수집 (모니터링용)
  logStats: 1
  statsUsers: "stats"

# 데이터베이스 연결
data:
  metadataSecretName: airflow-pgbouncer-secret
```

연결 수 계산 예시
```
# Airflow 컴포넌트별 연결 수
Scheduler: 10개 연결
Webserver: 10개 연결  
Triggerer: 5개 연결
Workers (3개): 각 5개 = 15개 연결
────────────────────────
총: 40개 클라이언트 연결

# PgBouncer 설정
pgbouncer:
  maxClientConn: 100      # 40개 + 여유분
  metadataPoolSize: 10    # PostgreSQL에 실제 10개만 연결
```
