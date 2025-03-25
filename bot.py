import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import StateFilter
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums.parse_mode import ParseMode
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import requests
import json
import io
import csv
import random
import string
from datetime import datetime, time
# Загрузка переменных окружения
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Конфигурация бота
TELEGRAM_BOT_TOKEN = os.getenv('TG_BOT_TOKEN')
FASTAPI_URL = os.getenv('FASTAPI_URL')
headers={os.getenv('FASTAPI_KEY_NAME'): os.getenv('FASTAPI_TOKEN')}
# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Состояния для FSM
class States(StatesGroup):
    mainmenu = State()
    delete_notification = State()  # Новое состояние для удаления уведомлений
    set_notification_time = State()

# Команда /start
@dp.message(StateFilter(None),Command('start'))
async def starting(sms: types.Message, state: FSMContext):
    try:
        # Проверяем, авторизован ли пользователь
        req = requests.get(f"{FASTAPI_URL}/check_id_user_tg/{sms.from_user.id}", headers=headers)
        print(req.text)
        print(req)
        if req.status_code == 404:
            await bot.send_message(sms.from_user.id, "Привет!\nДля авторизации введите: /auth {code}.")
        elif req.status_code == 200:
            await bot.send_message(sms.from_user.id, "Успешная авторизация. Добро пожаловать в главное меню!")
            id_user = json.loads(requests.get(f"{FASTAPI_URL}/get_id_user_by_id_user_tg/{sms.from_user.id}",headers=headers).text)['id_user']
            await state.update_data(id_user=id_user)
            await show_main_menu(sms.from_user.id)
            await state.set_state(States.mainmenu)
        else:
            await bot.send_message(sms.from_user.id, "Произошла ошибка.")
    except Exception as e:
        await bot.send_message(sms.from_user.id, "Произошла ошибка.")

# Команда /auth
@dp.message(StateFilter(None), Command('auth'))
async def auth_with_code(sms: types.Message, state: FSMContext):
    try:
        code = sms.text.split()[1]
        check_code = requests.get(f"{FASTAPI_URL}/check_auth_key/{code}",headers=headers)
        if check_code.status_code == 200:
            auth_user = requests.post(f"{FASTAPI_URL}/auth_user/?auth_key={code}&id_user_tg={sms.from_user.id}",headers=headers)
            if auth_user.status_code == 200:
                id_user = json.loads(requests.get(f"{FASTAPI_URL}/get_id_user_by_id_user_tg/{sms.from_user.id}",headers=headers).text)['id_user']
                await state.update_data(id_user=id_user)
                await state.set_state(States.mainmenu)
                await bot.send_message(sms.from_user.id, "Авторизация успешна! Добро пожаловать в главное меню.")
                await show_main_menu(sms.from_user.id)
            else:
                await bot.send_message(sms.from_user.id, "Произошла ошибка авторизации. Попробуйте снова.")
        else:
            await bot.send_message(sms.from_user.id, "Неверный код. Попробуйте снова.")
    except IndexError:
        await bot.send_message(sms.from_user.id, "Используйте команду в формате: /auth {code}.")
    except Exception as e:
        await bot.send_message(sms.from_user.id, "Произошла ошибка. Попробуйте позже.")

# Команда /weather
@dp.message(States.mainmenu, Command('weather'))
async def get_weather(sms: types.Message, state: FSMContext):
    user_data = await state.get_data()
    id_user = user_data['id_user']
    try:
        city_name = ' '.join(sms.text.split()[1:])
        if not city_name:
            # Если город не указан, используем домашний город
            user_info = json.loads(requests.get(f"{FASTAPI_URL}/get_user_by_id_user/{id_user}", headers=headers).text)
            city_name = user_info['home_city']
            if city_name == "unknown":
                await bot.send_message(sms.from_user.id, "Домашний город не установлен. Используйте /set_home_city {city}.")
                return

        # Запрос погоды
        weather_response = requests.get(f"{FASTAPI_URL}/weather_query/?id_user={id_user}&city={city_name}", headers=headers)
        if weather_response.status_code == 200:
            weather_data = weather_response.json()
            weather_message = (
                f"🌆 Город: {weather_data['weather'][0]}\n"
                f"🌤 Погода: {weather_data['weather'][1]}\n"
                f"📝 Описание: {weather_data['weather'][2]}\n"
                f"🌡 Температура: {weather_data['weather'][3]}°C\n"
                f"🤔 Ощущается как: {weather_data['weather'][4]}°C\n"
                f"💧 Влажность: {weather_data['weather'][5]}%\n"
                f"📊 Давление: {weather_data['weather'][6]} мм рт.ст.\n"
                f"💨 Скорость ветра: {weather_data['weather'][7]} м/с\n"
                f"🧭 Направление ветра: {weather_data['weather'][8]}\n"
                f"🌅 Восход: {weather_data['weather'][9]}\n"
                f"🌇 Закат: {weather_data['weather'][10]}\n"
                f"⏰ Время расчета данных: {weather_data['weather'][11]}"
            )

            # Получаем иконку погоды
            icon = weather_data['icon']  # Код иконки из API
            icon_path = f"icons/{icon}.png"  # Путь к иконке в папке icons

            try:
                # Отправляем фото с подписью
                with open(icon_path, "rb") as icon_file:
                    icon_bytes = icon_file.read()
                    icon_input_file = BufferedInputFile(icon_bytes, filename=f"{icon}.png")
                    await bot.send_photo(sms.from_user.id, icon_input_file, caption=weather_message, parse_mode=ParseMode.HTML)
            except FileNotFoundError:
                # Если иконка не найдена, отправляем сообщение без иконки
                await bot.send_message(sms.from_user.id, weather_message, parse_mode=ParseMode.HTML)
        else:
            await bot.send_message(sms.from_user.id, "Не удалось получить данные о погоде.")
    except Exception as e:
        await bot.send_message(sms.from_user.id, f"Произошла ошибка: {e}")

# Команда /set_home_city
@dp.message(States.mainmenu, Command('set_home_city'))
async def set_home_city(sms: types.Message, state: FSMContext):
    try:
        city_name = ' '.join(sms.text.split()[1:])
        if not city_name:
            await bot.send_message(sms.from_user.id, "Пожалуйста, укажите город.")
            return

        user_data = await state.get_data()
        id_user = user_data['id_user']
        set_city_response = requests.post(f"{FASTAPI_URL}/set_user_home_city/?id_user={id_user}&home_city={city_name}",headers=headers)
        if set_city_response.status_code == 200:
            await bot.send_message(sms.from_user.id, "Домашний город успешно установлен.")
        else:
            await bot.send_message(sms.from_user.id, "Произошла ошибка.")
    except Exception as e:
        await bot.send_message(sms.from_user.id, "Произошла ошибка.")

# Команда /history
@dp.message(States.mainmenu, Command('history'))
async def get_history(sms: types.Message, state: FSMContext):
    try:
        user_data = await state.get_data()
        id_user = user_data['id_user']
        history_response = requests.get(f"{FASTAPI_URL}/get_weather_history/{id_user}", headers=headers)
        if history_response.status_code == 200:
            history = history_response.json()
            if history:
                # Создаем CSV-файл в памяти
                csv_buffer = io.StringIO()
                csv_writer = csv.writer(csv_buffer)

                # Заголовки CSV
                csv_writer.writerow([
                    "Время запроса", "Город", "Погода", "Описание", "Температура (°C)",
                    "Ощущается как (°C)", "Влажность (%)", "Давление (мм рт.ст.)",
                    "Скорость ветра (м/с)", "Направление ветра", "Восход", "Закат", "Время расчета данных"
                ])

                # Записываем данные в CSV
                for record in history:
                    csv_writer.writerow([
                        record['query_timestamp'],  # Время запроса
                        record['city_name'],  # Город
                        record['weather_main'],  # Погода
                        record['weather_description'],  # Описание
                        round(record['temperature'],2),  # Температура
                        round(record['temperature_feels_like'],2),  # Ощущается как
                        record['humidity'],  # Влажность
                        record['pressure'],  # Давление
                        round(record['wind_speed'],2),  # Скорость ветра
                        record['wind_direction'],  # Направление ветра
                        record['sunrise'],  # Восход
                        record['sunset'],  # Закат
                        record['data_calculation'],  # Время расчета данных
                    ])

                # Преобразуем содержимое буфера в байты
                csv_buffer.seek(0)
                csv_bytes = csv_buffer.getvalue().encode('utf-8-sig')

                # Генерация уникального имени файла
                random_letter = random.choice(string.ascii_uppercase)
                random_digits = ''.join(random.choices(string.digits, k=3))
                random_letters = ''.join(random.choices(string.ascii_uppercase, k=3))
                filename = f"weather_history_{random_letter}{random_digits}{random_letters}.csv"

                # Отправляем CSV-файл пользователю
                csv_file = BufferedInputFile(csv_bytes, filename=filename)
                await bot.send_document(sms.from_user.id, csv_file, caption="📊 История запросов погоды")
            else:
                await bot.send_message(sms.from_user.id, "История запросов пуста.")
        else:
            await bot.send_message(sms.from_user.id, "Произошла ошибка.")
    except Exception as e:
        await bot.send_message(sms.from_user.id, "Произошла ошибка.")
# Функция для отображения главного меню
async def show_main_menu(user_id):
    menu = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="/weather"), KeyboardButton(text="/history")],
        [KeyboardButton(text="/set_home_city"), KeyboardButton(text="/set_name")],
        [KeyboardButton(text="/notification"), KeyboardButton(text="/delete_notification")],
        [KeyboardButton(text="/my_notifications")]  # Новая кнопка
    ], resize_keyboard=True)
    await bot.send_message(user_id, "Главное меню:", reply_markup=menu)
# Команда /notification
# Функция для отправки уведомления о погоде
async def send_weather_notification(id_user_tg: int,id_user: int, home_city: str,notification_time:str):
    try:
        user_info = requests.get(
            f"{FASTAPI_URL}/get_user_by_id_user/{id_user}",
            headers=headers
        ).json()
        print(user_info)
        greeting = get_greeting(notification_time)
        name = user_info.get('name')
        print(name)

        # Формируем приветствие
        caption = f"{greeting}{', ' + name if name else ''}!\n\n🌤 Текущий прогноз погоды:\n"
        # Запрос погоды для домашнего города
        weather_response = requests.get(f"{FASTAPI_URL}/weather_query/?id_user={id_user}&city={home_city}", headers=headers)
        if weather_response.status_code == 200:
            weather_data = weather_response.json()
            weather_message = (
                f"🌆 Город: {weather_data['weather'][0]}\n"
                f"🌤 Погода: {weather_data['weather'][1]}\n"
                f"📝 Описание: {weather_data['weather'][2]}\n"
                f"🌡 Температура: {weather_data['weather'][3]}°C\n"
                f"🤔 Ощущается как: {weather_data['weather'][4]}°C\n"
                f"💧 Влажность: {weather_data['weather'][5]}%\n"
                f"📊 Давление: {weather_data['weather'][6]} мм рт.ст.\n"
                f"💨 Скорость ветра: {weather_data['weather'][7]} м/с\n"
                f"🧭 Направление ветра: {weather_data['weather'][8]}\n"
                f"🌅 Восход: {weather_data['weather'][9]}\n"
                f"🌇 Закат: {weather_data['weather'][10]}\n"
                f"⏰ Время расчета данных: {weather_data['weather'][11]}"
            )

            # Получаем иконку погоды
            icon = weather_data['icon']  # Код иконки из API
            icon_path = f"icons/{icon}.png"  # Путь к иконке в папке icons

            try:
                # Отправляем фото с подписью
                with open(icon_path, "rb") as icon_file:
                    icon_bytes = icon_file.read()
                    icon_input_file = BufferedInputFile(icon_bytes, filename=f"{icon}.png")
                    await bot.send_photo(id_user_tg, icon_input_file, caption=caption+weather_message, parse_mode=ParseMode.HTML)
            except FileNotFoundError:
                # Если иконка не найдена, отправляем сообщение без иконки
                await bot.send_message(id_user_tg, weather_message, parse_mode=ParseMode.HTML)
        else:
            await bot.send_message(id_user_tg, "Не удалось получить данные о погоде.")
    except Exception as e:
        await bot.send_message(id_user_tg, f"Произошла ошибка: {e}")

# Функция для проверки и отправки уведомлений

# Модифицированная функция проверки уведомлений
async def check_notifications():
    while True:
        now = datetime.now().time().replace(second=0, microsecond=0)
        current_time_str = now.strftime('%H:%M')

        try:
            response = requests.get(
                f"{FASTAPI_URL}/get_notifications_by_time/?notification_time={current_time_str}",
                headers=headers
            )

            if response.status_code == 200:
                notifications = response.json()
                for notification in notifications:
                    await send_weather_notification(
                        notification['id_user_tg'],
                        notification['id_user'],
                        notification['home_city'],
                        current_time_str
                    )

        except Exception as e:
            logger.error(f"Ошибка проверки уведомлений: {str(e)}")

        await asyncio.sleep(60)
@dp.message(States.mainmenu, Command('notification'))
async def set_notification(sms: types.Message, state: FSMContext):
    try:
        user_data = await state.get_data()
        id_user = user_data['id_user']
        user_info = json.loads(requests.get(f"{FASTAPI_URL}/get_user_by_id_user/{id_user}", headers=headers).text)
        home_city = user_info['home_city']

        if home_city == "unknown":
            await bot.send_message(sms.from_user.id, "Домашний город не установлен. Используйте /set_home_city {city}.")
            return

        # Получаем время уведомления
        notification_time = sms.text.split()[1]
        try:
            time_obj = datetime.strptime(notification_time, '%H:%M').time()
        except ValueError:
            await bot.send_message(sms.from_user.id, "Неверный формат времени. Используйте формат HH:MM.")
            return

        # Сохраняем время уведомления в базу данных
        set_notification_response = requests.post(
            f"{FASTAPI_URL}/set_notification_time/?id_user={id_user}&notification_type=weather&notification_time={notification_time}",
            headers=headers
        )
        if set_notification_response.status_code == 200:
            await bot.send_message(sms.from_user.id, f"Уведомление установлено на {notification_time}.")
        else:
            await bot.send_message(sms.from_user.id, "Произошла ошибка при установке уведомления.")
    except IndexError:
        await bot.send_message(sms.from_user.id, "Используйте команду в формате: /notification HH:MM.")
    except Exception as e:
        await bot.send_message(sms.from_user.id, f"Произошла ошибка: {e}")
async def main():
    asyncio.create_task(check_notifications())  # Запуск фоновой задачи
    await dp.start_polling(bot)


@dp.message(States.mainmenu, Command('delete_notification'))
async def delete_notification(sms: types.Message, state: FSMContext):
    try:
        user_data = await state.get_data()
        id_user = user_data['id_user']

        # Получаем время уведомления
        notification_time = sms.text.split()[1]
        try:
            time_obj = datetime.strptime(notification_time, '%H:%M').time()
        except ValueError:
            await bot.send_message(sms.from_user.id, "Неверный формат времени. Используйте формат HH:MM.")
            return

        # Удаляем время уведомления из базы данных
        delete_notification_response = requests.delete(
            f"{FASTAPI_URL}/delete_notification_time/?id_user={id_user}&notification_time={notification_time}",
            headers=headers
        )
        if delete_notification_response.status_code == 200:
            await bot.send_message(sms.from_user.id, f"Уведомление на {notification_time} удалено.")
        else:
            await bot.send_message(sms.from_user.id, "Произошла ошибка при удалении уведомления.")
    except IndexError:
        await bot.send_message(sms.from_user.id, "Используйте команду в формате: /delete_notification HH:MM.")
    except Exception as e:
        await bot.send_message(sms.from_user.id, f"Произошла ошибка: {e}")


def get_greeting(notification_time: str) -> str:
    try:
        hour = int(notification_time.split(":")[0])
        if 6 <= hour < 11:
            return "Доброе утро"
        elif 11 <= hour < 16:
            return "Добрый день"
        elif 16 <= hour < 20:
            return "Добрый вечер"
        else:
            return "Доброй ночи"
    except:
        return "Доброго времени суток"

@dp.message(States.mainmenu, Command('set_name'))
async def set_name(sms: types.Message, state: FSMContext):
    try:
        user_data = await state.get_data()
        id_user = user_data['id_user']

        # Получаем имя пользователя
        name = ' '.join(sms.text.split()[1:])
        if not name:
            await bot.send_message(sms.from_user.id, "Пожалуйста, укажите имя.")
            return

        # Устанавливаем имя пользователя
        set_name_response = requests.post(
            f"{FASTAPI_URL}/set_user_name/?id_user={id_user}&user_name={name}",
            headers=headers
        )
        if set_name_response.status_code == 200:
            await bot.send_message(sms.from_user.id, f"Имя успешно установлено: {name}.")
        else:
            await bot.send_message(sms.from_user.id, "Произошла ошибка при установке имени.")
    except IndexError:
        await bot.send_message(sms.from_user.id, "Используйте команду в формате: /set_name Имя.")
    except Exception as e:
        await bot.send_message(sms.from_user.id, f"Произошла ошибка: {e}")
@dp.message(States.mainmenu, Command('my_notifications'))
async def get_my_notifications(sms: types.Message, state: FSMContext):
    try:
        user_data = await state.get_data()
        id_user = user_data['id_user']

        # Получаем список уведомлений через API
        response = requests.get(
            f"{FASTAPI_URL}/get_notifications_by_id_user/?id_user={id_user}",
            headers=headers
        )

        if response.status_code == 200:
            notifications = response.json()
            if notifications:
                # Формируем сообщение с уведомлениями
                message = ""
                for notification in notifications:
                    time_str = notification['notification_time'][:5]  # Обрезаем секунды
                    message += (
                        f"Время: {time_str}\n"
                        f"Тип: {notification['notification_type']}\n\n"
                    )
                await bot.send_message(sms.from_user.id, message.strip())
            else:
                await bot.send_message(sms.from_user.id, "У вас нет активных уведомлений.")
        else:
            await bot.send_message(sms.from_user.id, "Произошла ошибка при получении уведомлений.")
    except Exception as e:
        await bot.send_message(sms.from_user.id, f"Произошла ошибка: {e}")
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())