import telebot
import requests
import jsons
from Class_ModelResponse import ModelResponse

API_TOKEN = '8226018885:AAHv2bMa0a3bNyWXxtfwJpDQ3MBwwTlDyRY'
bot = telebot.TeleBot(API_TOKEN)

user_contexts = {}

MAX_CONTEXT_MESSAGES = 10

def get_user_context(user_id):
    """Получить контекст пользователя или создать новый с system prompt"""
    if user_id not in user_contexts:
        user_contexts[user_id] = [
            {
                "role": "system", 
                "content": """Ты - полезный русскоязычный ассистент. Отвечай только на русском языке. 
                
ВАЖНО: Внимательно запоминай всю информацию, которую сообщает пользователь:
- Имена и личные данные
- Даты и числа  
- Предпочтения и факты
- Историю диалога

Всегда используй эту информацию в последующих ответах."""
            }
        ]
    return user_contexts[user_id]

def add_user_message(user_id, message):
    """Добавить сообщение пользователя в контекст"""
    context = get_user_context(user_id)
    context.append({"role": "user", "content": message})
    
    if len(context) > MAX_CONTEXT_MESSAGES * 2:
        user_contexts[user_id] = context[-(MAX_CONTEXT_MESSAGES * 2):]

def add_assistant_message(user_id, message):
    """Добавить ответ ассистента в контекст"""
    context = get_user_context(user_id)
    context.append({"role": "assistant", "content": message})

def clear_context(user_id):
    """Очистить контекст пользователя"""
    if user_id in user_contexts:
        user_contexts[user_id] = []

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "Привет! Я ваш Telegram бот с поддержкой контекста!\n"
        "Доступные команды:\n"
        "/start - вывод всех доступных команд\n"
        "/model - выводит название используемой языковой модели\n"
        "/clear - очистить историю диалога\n"
        "/context - показать текущий контекст\n"
        "Отправьте любое сообщение, и я отвечу с учетом предыдущих сообщений."
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['model'])
def send_model_name(message):
    try:
        response = requests.get('http://127.0.0.1:1234/v1/models', timeout=5)
        if response.status_code == 200:
            model_info = response.json()
            model_name = model_info['data'][0]['id']
            bot.reply_to(message, f"Используемая модель: {model_name}")
        else:
            bot.reply_to(message, 'Не удалось получить информацию о модели.')
    except Exception as e:
        bot.reply_to(message, f'Ошибка при подключении к LM Studio: {e}')

@bot.message_handler(commands=['clear'])
def clear_user_context(message):
    user_id = message.from_user.id
    clear_context(user_id)
    bot.reply_to(message, "✅ История диалога очищена!")

@bot.message_handler(commands=['context'])
def show_context(message):
    user_id = message.from_user.id
    context = get_user_context(user_id)
    
    if not context:
        bot.reply_to(message, "История диалога пуста.")
        return
    
    context_text = "📝 Текущий контекст:\n\n"
    for i, msg in enumerate(context, 1):
        role = "👤 Вы" if msg["role"] == "user" else "🤖 Бот"
        context_text += f"{role}: {msg['content']}\n\n"
    
    if len(context_text) > 4000:
        context_text = context_text[:4000] + "\n\n... (контекст обрезан)"
    
    bot.reply_to(message, context_text)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    user_message = message.text
    
    try:
        add_user_message(user_id, user_message)
        
        context = get_user_context(user_id)
        
        print(f"👤 User {user_id}: {user_message}")
        print(f"📊 Размер контекста: {len(context)} сообщений")
        print(f"📋 Контекст: {context}")
        
        request = {
            "messages": context,
            "max_tokens": 500,
            "temperature": 0.7,
            "top_p": 0.9,
            "stream": False
        }
        
        print("Отправка запроса к LM Studio...")
        
        response = requests.post(
            'http://127.0.0.1:1234/v1/chat/completions',
            json=request,
            timeout=60
        )
        
        print(f"Статус ответа: {response.status_code}")
        
        if response.status_code == 200:
            model_response = jsons.loads(response.text, ModelResponse)
            assistant_reply = model_response.choices[0].message.content
            
            add_assistant_message(user_id, assistant_reply)
            
            bot.reply_to(message, assistant_reply)
            print(f"🤖 Ответ отправлен: {assistant_reply}")
            print(f"📈 Теперь в контексте: {len(get_user_context(user_id))} сообщений")
            
        else:
            if context and context[-1]["role"] == "user":
                context.pop()
            
            error_msg = f'Ошибка LM Studio: {response.status_code} - {response.text}'
            bot.reply_to(message, "Произошла ошибка при обращении к модели.")
            print(f"{error_msg}")
            
    except requests.exceptions.ConnectionError:
        context = get_user_context(user_id)
        if context and context[-1]["role"] == "user":
            context.pop()
        
        error_msg = "Не могу подключиться к LM Studio. Убедитесь, что программа запущена и модель загружена."
        bot.reply_to(message, error_msg)
        print(error_msg)
        
    except Exception as e:
        context = get_user_context(user_id)
        if context and context[-1]["role"] == "user":
            context.pop()
        
        error_msg = f'Произошла ошибка: {str(e)}'
        bot.reply_to(message, "Произошла ошибка при обработке сообщения.")
        print(f"{error_msg}")

def check_lm_studio_connection():
    try:
        response = requests.get('http://127.0.0.1:1234/v1/models', timeout=5)
        if response.status_code == 200:
            print("LM Studio подключен успешно")
            return True
        else:
            print("LM Studio не отвечает")
            return False
    except Exception as e:
        print(f"Ошибка подключения к LM Studio: {e}")
        return False

if __name__ == '__main__':
    if check_lm_studio_connection():
        print("🤖 Бот с поддержкой контекста запускается...")
        print("📝 Доступные команды: /start, /model, /clear, /context")
        bot.polling(none_stop=True)
    else:

        print("Сначала запустите LM Studio с загруженной моделью!")
