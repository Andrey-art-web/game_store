import httpx
import asyncio
import pytest


@pytest.mark.asyncio
async def test_webhook_parallel():
    # Открываем асинхронный HTTP-клиент (нужен для всех запросов)
    async with httpx.AsyncClient() as client:
        # Шаг 1: Создаём заказ
        order_response = await client.post(
            "http://127.0.0.1:8002/api/orders",
            json={
                "items": [
                    {"sku": "STEAM-TOPUP-500", "price": 500}
                ],
                "total_amount": 500
            }
        )
        order_id = order_response.json()["id"]
        print(f"Создан заказ с ID: {order_id}")

        # Шаг 2: Готовим 50 одинаковых вебхуков (у всех один event_id!)
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

        # Шаг 3: Запускаем все 50 вебхуков ОДНОВРЕМЕННО
        responses = await asyncio.gather(*tasks)

        # Шаг 4: Смотрим на ответы
        statuses = [r.json()["status"] for r in responses]
        print(f"Ответы от 50 вебхуков: {statuses}")

        # Шаг 5: Считаем, сколько accepted, сколько already_processed
        accepted_count = statuses.count("accepted")
        already_processed_count = statuses.count("already_processed")

        print(f"Принято: {accepted_count}")
        print(f"Уже обработано: {already_processed_count}")

        # Шаг 6: Проверки
        assert accepted_count == 1, f"Ошибка! Принято {accepted_count} вебхуков, а должно быть 1!"
        assert already_processed_count == 49, f"Ошибка! Уже обработано {already_processed_count}, а должно быть 49!"

        print("✅ ТЕСТ ПРОЙДЕН! Система выдержала 50 параллельных вебхуков и выдала товар ровно 1 раз!")