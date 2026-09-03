import httpx
import asyncio
import pytest


@pytest.mark.asyncio
async def test_webhook_parallel():
    # Сначала создаем заказ
    async with httpx.AsyncClient() as client:
        order_response = await client.post(
            "http://127.0.0.1:8002/api/orders",
            json={"sku": "STEAM-TOPUP-500"}
        )
        order_id = order_response.json()["id"]
        print(f"Создан заказ с ID: {order_id}")

        # Теперь шлём 50 одинаковых вебхуков ОДНОВРЕМЕННО
        tasks = []
        for i in range(50):
            tasks.append(client.post(
                "http://127.0.0.1:8002/webhook/payment",
                json={
                    "event_id": "evt_test_parallel_1",
                    "order_id": str(order_id),
                    "status": "paid",
                    "amount": 500,
                    "currency": "RUB",
                    "created_at": "2025-01-01T12:00:00Z"
                }
            ))

        responses = await asyncio.gather(*tasks)

        # Смотрим на ответы
        statuses = [r.json()["status"] for r in responses]
        print(f"Ответы от 50 вебхуков: {statuses}")

        # Проверяем, что только один вебхук получил статус "accepted"
        accepted_count = statuses.count("accepted")
        already_processed_count = statuses.count("already_processed")

        print(f"Принято: {accepted_count}")
        print(f"Уже обработано: {already_processed_count}")

        # Это ключевая проверка!
        assert accepted_count == 1, f"Ошибка! Принято {accepted_count} вебхуков, а должно быть 1!"
        assert already_processed_count == 49, f"Ошибка! Уже обработано {already_processed_count}, а должно быть 49!"

        print("✅ ТЕСТ ПРОЙДЕН! Система выдержала 50 параллельных вебхуков и выдала товар ровно 1 раз!")