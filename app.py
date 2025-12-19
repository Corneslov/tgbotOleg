from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from model import OlegBotModel
from survey_utils import parse_survey_data, validate_survey_data
from db_config import get_db_config
import json

# Токен вашего бота
TELEGRAM_BOT_TOKEN = "8422959456:AAGR2GTyW1hkCzFvxm7JB6ImHVSwuZcL1Ds"  # Замените на реальный токен

# URL вашего веб-приложения
WEBAPP_URL = "https://tgbot-oleg.vercel.app/"  # Замените на реальный URL

# Инициализация модели базы данных
db_model = OlegBotModel(**get_db_config())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    print("\n🔵 СОБЫТИЕ: Нажата команда /start")
    user = update.effective_user
    print(f"👤 Пользователь: {user.first_name} {user.last_name or ''} (ID: {user.id})")
    
    # Проверяем, существует ли пользователь в базе данных
    existing_user = db_model.get_user_by_telegram_id(user.id)
    print(f"💾 Пользователь в БД: {'Найден' if existing_user else 'Не найден'}")
    
    if existing_user and existing_user['name']:
        # Пользователь существует и имя есть в базе данных
        await update.message.reply_text(
            f"С возвращением, {existing_user['name']}!"
        )
        
        # Создаем клавиатуру с кнопкой для открытия веб-приложения
        keyboard = [
            [InlineKeyboardButton(
                "📝 Заполнить опросник",
                web_app=WebAppInfo(url=WEBAPP_URL)
            )]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        print(f"✅ Отправляем кнопку 'Заполнить опросник' с URL: {WEBAPP_URL}")
        await update.message.reply_text(
            "Нажмите на кнопку ниже, чтобы заполнить опросник:",
            reply_markup=reply_markup
        )
    else:
        # Новый пользователь или пользователь без имени в базе данных
        if not existing_user:
            # Создаем нового пользователя с пустым именем
            db_model.create_user(
                telegram_id=user.id,
                name="",  # Пустое имя, пользователь введет его позже
                comment=f"Username: @{user.username}" if user.username else None
            )
            await update.message.reply_text(
                "Добро пожаловать! Вы зарегистрированы в системе."
            )
        else:
            await update.message.reply_text(
                "Рад видеть вас снова!"
            )
        
        # Запрашиваем имя у пользователя
        await update.message.reply_text(
            "Пожалуйста, введите ваше имя:"
        )
        
        # Устанавливаем состояние ожидания имени
        db_model.create_or_update_state(
            telegram_id=user.id,
            state="waiting_for_name",
            state_data={}
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help"""
    await update.message.reply_text(
        "Этот бот поможет вам провести опрос по переговорам.\n\n"
        "Доступные команды:\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать это сообщение\n"
        "/survey - Начать новый опрос\n"
        "/results - Посмотреть результаты предыдущих опросов"
    )

async def survey_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /survey"""
    print("\n🔵 СОБЫТИЕ: Нажата команда /survey")
    user = update.effective_user
    print(f"👤 Пользователь: {user.first_name} (ID: {user.id})")
    
    # Проверяем, существует ли пользователь в базе данных и есть ли у него имя
    existing_user = db_model.get_user_by_telegram_id(user.id)
    print(f"💾 Пользователь в БД: {'Найден' if existing_user else 'Не найден'}")
    
    if not existing_user or not existing_user['name']:
        # Пользователь не существует или у него нет имени
        await update.message.reply_text(
            "Пожалуйста, сначала введите ваше имя. Используйте команду /start для регистрации."
        )
        return
    
    # Создаем клавиатуру с кнопкой для открытия веб-приложения
    keyboard = [
        [InlineKeyboardButton(
            "📝 Заполнить опросник",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    print(f"✅ Отправляем кнопку 'Заполнить опросник' с URL: {WEBAPP_URL}")
    await update.message.reply_text(
        "Нажмите на кнопку ниже, чтобы заполнить опросник:",
        reply_markup=reply_markup
    )

async def results_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /results"""
    user = update.effective_user
    
    # Получаем все опросы пользователя
    surveys = db_model.get_surveys_by_telegram_id(user.id)
    
    if not surveys:
        await update.message.reply_text("У вас пока нет сохраненных опросов.")
        return
    
    response_text = f"Ваши опросы (всего: {len(surveys)}):\n\n"
    
    for i, survey in enumerate(surveys[:5], 1):  # Показываем только последние 5 опросов
        created_at = survey['created_at'].strftime("%d.%m.%Y %H:%M") if survey['created_at'] else "Неизвестно"
        problem = survey['survey_data'].get('problem', 'Без темы')
        response_text += f"{i}. {created_at}\n"
        response_text += f"   Тема: {problem[:50]}{'...' if len(problem) > 50 else ''}\n\n"
    
    await update.message.reply_text(response_text)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений"""
    user = update.effective_user
    text = update.message.text
    
    # Получаем текущее состояние пользователя
    user_state = db_model.get_state_by_telegram_id(user.id)
    
    if user_state and user_state['state'] == 'waiting_for_name':
        # Пользователь вводит имя
        name = text.strip()
        
        if len(name) < 2:
            await update.message.reply_text("Имя слишком короткое. Пожалуйста, введите ваше имя:")
            return
        
        # Обновляем имя пользователя в базе данных
        existing_user = db_model.get_user_by_telegram_id(user.id)
        if existing_user:
            db_model.update_user(existing_user['id'], name=name)
        
        # Обновляем состояние пользователя
        db_model.create_or_update_state(
            telegram_id=user.id,
            state="name_entered",
            state_data={}
        )
        
        await update.message.reply_text(
            f"Спасибо, {name}! Теперь вы можете заполнить опросник."
        )
        
        # Создаем клавиатуру с кнопкой для открытия веб-приложения
        keyboard = [
            [InlineKeyboardButton(
                "📝 Заполнить опросник",
                web_app=WebAppInfo(url=WEBAPP_URL)
            )]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Нажмите на кнопку ниже, чтобы заполнить опросник:",
            reply_markup=reply_markup
        )

async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик данных от веб-приложения"""
    user = update.effective_user
    data = update.message.web_app_data.data

    print("\n" + "=" * 80)
    print("🟢 СОБЫТИЕ: НАЖАТА КНОПКА 'ОТПРАВИТЬ РЕЗУЛЬТАТЫ' В ВЕБ-ПРИЛОЖЕНИИ")
    print("=" * 80)
    print(f"👤 От пользователя: {user.first_name} {user.last_name or ''} (ID: {user.id})")
    print(f"📦 Размер данных: {len(data)} символов")
    print(f"📝 Первые 200 символов данных: {data[:200]}...")
    
    try:
        # Парсим JSON данные
        json_data = json.loads(data)
        print(f"JSON успешно распарсен. Ключи: {list(json_data.keys())}")
        
        # Выводим структуру данных для отладки
        if 'user' in json_data:
            print(f"Структура user: {list(json_data['user'].keys())}")
        if 'survey' in json_data:
            print(f"Структура survey: {list(json_data['survey'].keys())}")
            if 'data' in json_data['survey']:
                print(f"Структура survey.data: {list(json_data['survey']['data'].keys())}")
        
        # Используем утилиты для обработки данных
        parsed_data = parse_survey_data(json_data)
        if not parsed_data:
            print("ОШИБКА: Не удалось обработать данные опроса")
            await update.message.reply_text("Ошибка при обработке данных опроса.")
            return
        
        telegram_id = parsed_data['telegram_id']
        survey_data = parsed_data['survey_data']
        
        print(f"Telegram ID из данных: {telegram_id}")
        print(f"Основные поля опроса:")
        print(f"  - Проблема: {survey_data.get('problem', 'Не указано')[:50]}...")
        print(f"  - Истинная цель: {survey_data.get('true_goal', 'Не указано')[:50]}...")
        print(f"  - Кто был: {survey_data.get('who_was_it', 'Не указано')[:50]}...")
        
        # Проверяем, что данные от того же пользователя
        if telegram_id != user.id:
            print(f"ОШИБКА: Несоответствие ID пользователя. Ожидался {user.id}, получен {telegram_id}")
            await update.message.reply_text("Ошибка: несоответствие данных пользователя.")
            return
        
        # Валидация данных
        is_valid, error_message = validate_survey_data(survey_data)
        if not is_valid:
            print(f"ОШИБКА ВАЛИДАЦИИ: {error_message}")
            await update.message.reply_text(f"Ошибка валидации: {error_message}")
            return
        
        print("Данные прошли валидацию")
        
        # Получаем пользователя из базы данных
        existing_user = db_model.get_user_by_telegram_id(user.id)
        print(f"Пользователь в БД: {'Найден' if existing_user else 'Не найден'}")
        
        # Сохраняем опрос
        survey = db_model.create_survey(
            telegram_id=user.id,
            user_id=existing_user['id'] if existing_user else None,
            survey_data=survey_data
        )
        
        if survey:
            print(f"ОПРОС УСПЕШНО СОХРАНЕН. ID опроса: {survey.get('id')}")
            # Обновляем состояние пользователя
            db_model.create_or_update_state(
                telegram_id=user.id,
                state="survey_completed",
                state_data={"last_survey_id": survey['id']}
            )
            
            print("=" * 80)
            print("✅ УСПЕХ! ОТПРАВЛЯЕМ ПОДТВЕРЖДЕНИЕ ПОЛЬЗОВАТЕЛЮ")
            print("=" * 80)
            await update.message.reply_text(
                "✅ Спасибо! Ваш опрос успешно сохранен.\n"
                "Используйте команду /results, чтобы посмотреть все ваши опросы."
            )
        else:
            print("ОШИБКА: Не удалось сохранить опрос в БД")
            await update.message.reply_text("Ошибка при сохранении опроса. Попробуйте еще раз.")
            
    except json.JSONDecodeError as e:
        print(f"ОШИБКА JSON: {e}")
        await update.message.reply_text("Ошибка формата данных. Попробуйте еще раз.")
    except Exception as e:
        print(f"НЕИЗВЕСТНАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text("Произошла ошибка. Попробуйте еще раз.")
    
    print("=" * 80 + "\n")

def main() -> None:
    """Основная функция запуска бота"""
    print("=" * 80)
    print("🚀 БОТ ЗАПУСКАЕТСЯ")
    print("=" * 80)
    print(f"📝 Токен бота: {TELEGRAM_BOT_TOKEN[:20]}...")
    print(f"🌐 URL веб-приложения: {WEBAPP_URL}")
    print(f"💾 База данных: {get_db_config()['host']}/{get_db_config()['database']}")
    print("=" * 80)
    
    # Создаем приложение
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("survey", survey_command))
    application.add_handler(CommandHandler("results", results_command))
    
    # Добавляем обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # Добавляем обработчик данных от веб-приложения
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
    
    print("✅ Обработчики зарегистрированы:")
    print("   - /start")
    print("   - /help")
    print("   - /survey")
    print("   - /results")
    print("   - Текстовые сообщения")
    print("   - ⭐ Web App Data (ВАЖНО!)")
    print("=" * 80)
    print("🟢 БОТ ЗАПУЩЕН И ГОТОВ К РАБОТЕ!")
    print("=" * 80)
    
    # Запускаем бота
    application.run_polling()

if __name__ == "__main__":
    main()
