# Reference ERD Model on (Postgre)

## BaseModel
    TenantId, CreateAt, CreateBy, UpdateAt, UpdateBy, DeleteAT, DeleteBy, IsActive, IsDeleted

## Site Setup

### Tenant
    TenantId, TenantCode, TenantName, IsActive, IsDeleted, CreatedAt, CreatedBy
### User
    UserId, TenantId,   UserName, PasswordHash, IsActive, IsDeleted
### Site
    SiteId, TenantId,   SiteCode, SiteName, Location, IsActive, IsDeleted, CreatedAt, CreatedBy
### Gateway
    GatewayId TenantId SiteId   GatewayCode IPAddress FirmwareVersion IsOnline Lastseen
### Asset
    AssetId, TenantId, SiteId, GatewayId,  AssetCode, AssetName, AssetType
### Sensor
    SensorId TenantId AssetId GatewayId SensorCode SensorType  MountLocation  ValidationData, InstallationDate IsActive
### AssetHealth
    AssetHealthId TenantId SiteId AssetId   HealthScore HealthStatus CalculationMethod HealthCalcDate
    
field Notes:	
Asset: AssetType	('-- motor, pump, ..')
Sensor: GatewayId	('-- NULL if direct-to-broker else Gateway-based sensor')
Sensor: SensorType	('-- vibration, temperature, ...')
Sensor: MountLocation	('-- motor_DE, motor_NDE, ...')
AssetHealth: HealthScore	('-- 0 to 100')
AssetHealth: HealthStatus	('-- Healthy, Warning, Critical,...')
    
## Prediction	
### TelemetryRaw
    MeasureRawId TenantId SiteId Asset SensorId --NULL   TimestampUtc PayloadOriginal PayloadNormalized ValidationData 
### Prediction
    PredictionId TenantId SiteId Asset SensorId --NULL MeasureRawId   PayloadNormalized ValidationData   TimestampUtc PredictionLabel Probability ModelVersionId ExplanationPayload
### Feedback
    FeedbackId TenantId SiteId Asset SensorId --NULL PredictionId   PayloadNormalized ValidationData PredictionLabel Probability   NewLabel Correction CreatedAt CreatedBy
    
## ML Management	
### MLModel
    ModelId TenantId  ModelName  ModelDescription  ModelType IsActive CreatedAt
### MLModelVersion
    ModelVersionId TenantId ModelId  SemanticVersion FullVersionLabel Stage ModelArtifactPath DockerImageTag DatasetHash FeatureSchemaHash  TrainingStart  TrainingEnd  Accuracy  PrecisionScore  RecallScore  F1Score  FalseAlarmRate    IsActive CreatedAt
### MLModelDeployment
    DeploymentId  TenantId  ModelId  ModelVersionId   IsProduction  DeploymentStart  DeploymentEnd   RollbackFromVersionId  CreatedAt
### AssetModelVersion
    AssetModelDeploymentId TenantId  AssetId  ModelId  ModelVersionId  Stage DeploymentStart  DeploymentEnd   IsActive CreatedAt
    
field Notes:	
MLModel: ModelName	example ('-- fault_classifier')
MLModel: ModelType	example ('-- Classification, Regression, RUL, ..')  
MLModelVersion: SemanticVersion	example ('-- 1.0.3')  
MLModelVersion: FullVersionLabel	example ('-- fault_classifier:1.0.3')
MLModelVersion: Stage	example  ('-- staging, production, archived')
    
## Alert Management	
### NotificationType
    NotificationTypeId TenantId NotifyTypeName NotifyTypeData 
### AlarmRule
    AlarmRuleId TenantId AssetId SensorId   RuleName ParameterName ThresholdValue ComparisonOperator SeverityLevel
### AlarmNotificationType
    TenantId AlarmRuleId NotoficationTypeId
### AlarmEvent
    AlarmEventId TenantId AssetId SensorId AlarmRuleId PredictionId   ModelVersionId TriggeredValue TriggeredAt ClearedAt CorrectionPlan   Status AcknowledgedBy AcknowledgedAt 
### NotificationLog
    NotificationLogId TenantId AssetId AlarmEventId   ..
### MaintenanceWorkOrder
    WorkOrderId TenantId AssetId AlarmEventId   WorkNumber Dewscription PriorityLevel   Status AssignedTo
    
## Chatbot	
### KnowledgeBase
    KnowledgeId TenantId   Title Category AssetType  FaultType  SeverityLevel  Symptoms RootCause RecommendedAction ReferenceStandard  Tags  IsGlobal  IsActive CreatedBy  CreatedAt UpdatedAt
### KnowledgeEmbedding
    EmbeddingId TenantId KnowledgeId  EmbeddingVector  ModelName CreatedAt
### Conversation

### Message


Notes:	
KnowledgeBase: Category	'-- Bearing, Misalignment, Cavitation, etc.'
KnowledgeBase: AssetType	'-- motor, pump, gearbox'
KnowledgeBase: FaultType	'-- Unbalance, Looseness, BearingOuterRace'
KnowledgeBase:SeverityLevel	'-- 1=Low,2=Medium,3=High,4=Critical'
KnowledgeBase: RootCause	'-- vibration patterns, temperature rise'
KnowledgeBase: ReferenceStandard	'-- e.g. ISO10816'
KnowledgeBase: Tags	'-- comma-separated or JSON'
KnowledgeBase: IsGlobal	'-- 0 = Tenant-specific -- 1 = Shared global knowledge (SaaS master data)'
KnowledgeEmbedding: EmbeddingVector	'-- Store serialized float array or use external vector DB'
