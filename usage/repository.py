class MongoQuotaStore:
    def __init__(self, collection, day_provider):
        self.collection = collection
        self.day_provider = day_provider

    def reserve(
        self,
        identifier: str,
        task_token: str,
        byte_count: int,
        limit_bytes: int,
        active_limit: int,
    ) -> bool:
        document_id = f"{self.day_provider().isoformat()}:{identifier}"
        self.collection.update_one(
            {"_id": document_id},
            {
                "$setOnInsert": {
                    "identifier": identifier,
                    "day": self.day_provider().isoformat(),
                    "charged_bytes": 0,
                    "reserved_bytes": 0,
                    "active_tasks": 0,
                    "reservations": [],
                }
            },
            upsert=True,
        )

        existing = self.collection.find_one(
            {"_id": document_id, "reservations.task_token": task_token},
            {"_id": 1},
        )
        if existing:
            return True

        result = self.collection.update_one(
            {
                "_id": document_id,
                "reservations.task_token": {"$ne": task_token},
                "active_tasks": {"$lt": active_limit},
                "$expr": {
                    "$lte": [
                        {
                            "$add": [
                                "$charged_bytes",
                                "$reserved_bytes",
                                byte_count,
                            ]
                        },
                        limit_bytes,
                    ]
                },
            },
            {
                "$inc": {"reserved_bytes": byte_count, "active_tasks": 1},
                "$push": {"reservations": {"task_token": task_token, "bytes": byte_count}},
            },
        )
        return result.modified_count == 1

    def release(self, identifier: str, task_token: str, byte_count: int) -> None:
        document_id = f"{self.day_provider().isoformat()}:{identifier}"
        self.collection.update_one(
            {"_id": document_id, "reservations.task_token": task_token},
            {
                "$inc": {"reserved_bytes": -byte_count, "active_tasks": -1},
                "$pull": {"reservations": {"task_token": task_token}},
            },
        )

    def settle(
        self,
        identifier: str,
        task_token: str,
        *,
        reserved_bytes: int,
        actual_bytes: int,
    ) -> bool:
        document_id = f"{self.day_provider().isoformat()}:{identifier}"
        result = self.collection.update_one(
            {"_id": document_id, "reservations.task_token": task_token},
            {
                "$inc": {
                    "reserved_bytes": -reserved_bytes,
                    "charged_bytes": actual_bytes,
                    "active_tasks": -1,
                },
                "$pull": {"reservations": {"task_token": task_token}},
            },
        )
        return result.modified_count == 1
