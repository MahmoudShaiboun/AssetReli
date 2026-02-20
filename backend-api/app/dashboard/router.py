from datetime import datetime

from fastapi import APIRouter, Depends

from app.auth.schemas import UserOut
from app.common.database import get_mongo_db
from app.common.dependencies import get_current_user_with_tenant

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(
    current_user: UserOut = Depends(get_current_user_with_tenant),
    db=Depends(get_mongo_db),
):
    tenant_filter = {"tenant_id": str(current_user.effective_tenant_id)}

    total_predictions = await db.sensor_readings.count_documents(
        {"prediction": {"$exists": True}, **tenant_filter}
    )
    total_feedback = await db.feedback.count_documents(tenant_filter)

    latest_readings = (
        await db.sensor_readings.find(
            {"prediction": {"$exists": True}, **tenant_filter}
        )
        .sort("timestamp", -1)
        .limit(20)
        .to_list(20)
    )

    for reading in latest_readings:
        reading["_id"] = str(reading["_id"])

    anomaly_count = sum(
        1
        for r in latest_readings
        if r.get("prediction") and r["prediction"].lower() != "normal"
    )

    return {
        "total_predictions": total_predictions,
        "total_feedback": total_feedback,
        "latest_readings": latest_readings,
        "recent_anomalies": anomaly_count,
        "timestamp": datetime.utcnow().isoformat(),
    }
