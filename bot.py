import os
import json
import boto3
import requests
import pybase64

BOT_TOKEN = os.getenv("TG_BOT_KEY")
YANDEX_IAM_KEY = os.getenv("YANDEX_IAM_KEY")
YANDEX_GPT_BUCKET = os.getenv("YANDEX_GPT_BUCKET")
YANDEX_GPT_OBJECT = os.getenv("YANDEX_GPT_OBJECT")
YANDEX_STORAGE_ACCESS_KEY = os.getenv("YANDEX_STORAGE_ACCESS_KEY")
YANDEX_STORAGE_SECRET_KEY = os.getenv("YANDEX_STORAGE_SECRET_KEY")
YANDEX_USER_KEY = os.getenv("YANDEX_USER_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

s3_client = boto3.client(
    "s3",
    endpoint_url="https://storage.yandexcloud.net",  
    aws_access_key_id=YANDEX_STORAGE_ACCESS_KEY,
    aws_secret_access_key=YANDEX_STORAGE_SECRET_KEY,
)

def handler(event, context):
    try:
        data = json.loads(event.get('body'))
    except Exception as e:
        print(f"Ошибка чтения JSON: {e}")
        return {"statusCode": 400, "body": f"Invalid JSON: {e}"}
    
    print(f"Полученные данные: {data}")

    if "message" not in data:
        print("Нет сообщения в обновлении Telegram")
        return {"statusCode": 200, "body": "No message in update"}

    message = data["message"]
    chat_id = message["chat"]["id"]

    if "text" in message:
        text = message["text"]

        if text == "/start":
            send_message(chat_id, "Я помогу подготовить ответ на экзаменационный вопрос по дисциплине \"Операционные системы\".\nПришлите мне фотографию с вопросом или наберите его текстом.")
        elif text == "/help":
            send_message(chat_id, "Пришлите текст или фото с экзаменационным вопросом, и я постараюсь вам помочь!")
        else:
            answer = handle_text_question(text)
            send_message(chat_id, answer)
    
    elif "photo" in message:
        handle_photo_message(message, chat_id)
    
    else:
        send_message(chat_id, "Я могу обработать только текстовые сообщения или фотографии.")

    return {"statusCode": 200, "body": "OK"}

def send_message(chat_id, text):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        response = requests.post(url, json=payload)
        print(f"Ответ Telegram API: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"Ошибка отправки сообщения: {e}")

def handle_text_question(question):
    print("Загрузка инструкции для YandexGPT...")
    instruction = get_instruction_from_storage()
    if not instruction:
        print("Инструкция не загружена!")
        return "Не удалось загрузить инструкцию для YandexGPT."

    print("Отправка вопроса в YandexGPT...")
    response = send_to_yandex_gpt(question, instruction)
    if response:
        print("Ответ от YandexGPT успешно получен.")
        return response
    else:
        print("Не удалось получить ответ от YandexGPT.")
        return "Я не смог подготовить ответ на ваш вопрос."

def get_instruction_from_storage():
    try:
        print(f"Попытка загрузить объект '{YANDEX_GPT_OBJECT}' из бакета '{YANDEX_GPT_BUCKET}'")
        obj = s3_client.get_object(Bucket=YANDEX_GPT_BUCKET, Key=YANDEX_GPT_OBJECT)
        instruction_str = obj["Body"].read().decode("utf-8") 
        instruction = json.loads(instruction_str) 
        print("Инструкция успешно загружена.")
        return instruction['instruction']
    except Exception as e:
        print(f"Ошибка загрузки инструкции: {e}")
    return None

def send_to_yandex_gpt(question, instruction):
    try:
        url = 'https://llm.api.cloud.yandex.net/foundationModels/v1/completion' 
        text = instruction + " " + question
        response = requests.post(
            url, 
            headers={
                "Authorization": f"Api-Key {YANDEX_USER_KEY}",
                "x-folder-id": YANDEX_FOLDER_ID,
                "Content-Type": "application/json"
            }, 
            json={
                "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite/latest",
                "completionOptions": {"maxTokens":500,"temperature":0.6},
                "messages": 
                    [
                        {"role":"user","text":text}
                    ]
            }
        )
        if response.status_code == 200:
            response = response.json()
            ans = response['result']['alternatives'][0]['message']['text']
            ans = ans.replace("**", "")
            return ans
    except Exception as e:    
        print(f"Ошибка: {e}")
    return None

def handle_photo_message(message, chat_id):
    photo = message["photo"][-1] 
    file_id = photo["file_id"]
    file_url = get_file_url(file_id)

    if not file_url:
        send_message(chat_id, "Не удалось загрузить фотографию.")
        return

    recognized_text = recognize_text_from_image(file_url)
    if not recognized_text:
        send_message(chat_id, "Я не смог распознать текст с этой фотографии.")
        return

    answer = handle_text_question(recognized_text)
    send_message(chat_id, answer)

def get_file_url(file_id):
    url = f"{TELEGRAM_API_URL}/getFile"
    response = requests.get(url, params={"file_id": file_id}).json()

    if response.get("ok"):
        file_path = response["result"]["file_path"]
        return f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    return None

def recognize_text_from_image(file_url):
    try:
        image_data = requests.get(file_url).content
    except Exception as e:
        print(f"Ошибка загрузки изображения: {e}")
        return None

    image_base64 = pybase64.b64encode(image_data).decode("utf-8")
    headers = {
        "Authorization": f"Api-Key {YANDEX_USER_KEY}",
        "Content-Type": "application/json",
        "x-folder-id": YANDEX_FOLDER_ID
    }
    data = {
        "analyzeSpecs": [
            {
                "content": image_base64,
                "features": [
                    {
                        "type": "TEXT_DETECTION",
                        "textDetectionConfig": {
                            "languageCodes": [
                                "ru"
                            ],
                            "model": "page"
                        }
                    }
                ]
            }
        ],
        "folderId": YANDEX_FOLDER_ID
    }

    try:
        response = requests.post(
            "https://vision.api.cloud.yandex.net/vision/v1/batchAnalyze",
            headers=headers,
            json=data
        )
        recognized_text = ""
        
        if response.status_code == 200:
            ocr_result = response.json()
            print(f"Результат OCR: {ocr_result}") 


            if "results" not in ocr_result or not ocr_result["results"]:
                print("Нет данных в ключе 'results'")
                return recognized_text

            for result_index, result in enumerate(ocr_result["results"]):
                print(f"\nОбработка result[{result_index}]...")
                
                if "results" not in result or not result["results"]:
                    print(f"Нет данных в result[{result_index}]['results']")
                    continue
                
                text_detection = result["results"][0].get("textDetection", {})
                if not text_detection:
                    print(f"textDetection пуст для result[{result_index}]")
                    continue
                
                print(f"textDetection найден для result[{result_index}]: {text_detection.keys()}")

                pages = text_detection.get("pages", [])
                if not pages:
                    print(f"Нет данных в pages для result[{result_index}]")
                    continue
                
                print(f"Найдено страниц: {len(pages)}")

                for page_index, page in enumerate(pages):
                    print(f"\nОбработка page[{page_index}]...")

                    print(f"Содержимое page[{page_index}]: {page.keys()}")

                    for block_index, block in enumerate(page.get("blocks", [])):
                        print(f"Обработка block[{block_index}]...")
                        print(f"Содержимое block[{block_index}]: {block.keys()}")

                        for line_index, line in enumerate(block.get("lines", [])):
                            print(f"Обработка line[{line_index}]...")
                            print(f"Содержимое line[{line_index}]: {line.keys()}")

                            for word_index, word in enumerate(line.get("words", [])):
                                word_text = word.get("text", "")
                                print(f"Слово[{word_index}]: '{word_text}'")
                                recognized_text += word_text + " "
                                print(recognized_text)

        else:
            print(response.status_code)
        return recognized_text
    except Exception as e:
        print(f"Ошибка OCR запроса: {e}")
    return None