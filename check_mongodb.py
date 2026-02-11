"""
Check what's in MongoDB sensor_readings
"""
import pymongo

client = pymongo.MongoClient("mongodb://admin:admin123@localhost:27017/")
db = client["assetreli"]

# Get latest 10 predictions
readings = db.sensor_readings.find({}, {
    "sensor_id": 1,
    "prediction": 1,
    "confidence": 1,
    "timestamp": 1,
    "_id": 0
}).sort("timestamp", -1).limit(10)

print("="*80)
print("  LATEST 10 PREDICTIONS IN MONGODB")
print("="*80)

for i, reading in enumerate(readings, 1):
    print(f"\n{i}. Sensor: {reading.get('sensor_id', 'N/A')}")
    print(f"   Prediction: {reading.get('prediction', 'N/A')}")
    print(f"   Confidence: {reading.get('confidence', 0):.2f}")
    print(f"   Time: {reading.get('timestamp', 'N/A')}")

# Count by prediction type
print("\n" + "="*80)
print("  PREDICTION SUMMARY")
print("="*80)

pipeline = [
    {"$match": {"prediction": {"$ne": None}}},
    {"$group": {"_id": "$prediction", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}}
]

for result in db.sensor_readings.aggregate(pipeline):
    print(f"{result['_id']}: {result['count']}")

client.close()
