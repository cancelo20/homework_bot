import logging
import time
import os

import requests
import telegram

from dotenv import load_dotenv
from http import HTTPStatus


load_dotenv()


PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}


HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания."
}


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter(
    "%(asctime)s, %(levelname)s, %(message)s")

handler = logging.StreamHandler()
handler.setFormatter(formatter)

logger.addHandler(handler)


def check_tokens():
    """Проверка доступности переменных окружения"""
    if PRACTICUM_TOKEN is None:
        logger.critical("Ошибка импорта Practicum token")
        return False
    elif TELEGRAM_TOKEN is None or TELEGRAM_CHAT_ID is None:
        logger.critical("Ошибка импорта TG token или chat id")
        return False
    else:
        return True


def send_message(bot, message):
    """Функция отправки сообщения пользователю"""
    try:
        bot.send_message(str(TELEGRAM_CHAT_ID), message)
        logger.debug(f"Успешная отправка сообщения ({message})")
    except Exception as error:
        logger.error(f"Сообщение не отправлено: {error}")


def get_api_answer(timestamp):
    """Получение ответа от запрашиваемого API"""
    params = {"from_date": timestamp}

    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        raise SystemError(f"Ошибка получения запроса: {error}")
    else:
        status_code = homework_statuses.status_code
        if status_code == HTTPStatus.OK:
            return homework_statuses.json()
        elif status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
            raise SystemError(
                f"status code == {HTTPStatus.INTERNAL_SERVER_ERROR.value}")
        elif status_code == HTTPStatus.REQUEST_TIMEOUT:
            raise SystemError(
                f"status code == {HTTPStatus.REQUEST_TIMEOUT.value}")
        else:
            raise SystemError("возвращен status code отличный от 200")


def check_response(response):
    """Проверка ответа API на соответсвие документации"""
    if type(response) is dict:
        if "homeworks" in response:
            homeworks = response["homeworks"]
            if type(homeworks) == list:
                return homeworks
            else:
                raise TypeError("Значение ключа homeworks не словарь")
        else:
            raise KeyError("Отсутсвует ключ homeworks в ответе API")
    else:
        raise TypeError("В ответе API получен не словарь")


def parse_status(homework):
    """Вердикт изменения статуса домашней работы"""
    homework_name = homework.get("homework_name")
    homework_status = homework.get("status")

    if homework_name is not None and homework_status is not None:
        if homework_status in HOMEWORK_VERDICTS:
            verdict = HOMEWORK_VERDICTS.get(homework_status)
            return ('Изменился статус проверки '
                    + f'работы "{homework_name}". {verdict}')
        else:
            raise SystemError("Неизвестный статус домашней работы")
    else:
        raise KeyError("Значения ключей homework_name и status отсутсвуют")


def main():
    """Основная логика работы бота."""
    LAST_HOMEWORK_COUNTER = 0

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 0
    hw_status_check = "cheking status"

    while True:
        if check_tokens() is True:
            try:
                response = get_api_answer(timestamp)
                response = check_response(response)

                homework_verdict = parse_status(
                    response[LAST_HOMEWORK_COUNTER])

                hw_status = response[LAST_HOMEWORK_COUNTER].get("status")

                if hw_status != hw_status_check:
                    hw_status_check = hw_status
                    send_message(bot, homework_verdict)
                else:
                    logger.info(
                        "Всё сработало, но "
                        + "статус работы не изменился, "
                        + "сообщение не будет отправлено.")
            except Exception as error:
                message = f"Сбой в работе программы: {error}"
                logger.error(message)
            finally:
                time.sleep(RETRY_PERIOD)
        else:
            break


if __name__ == "__main__":
    main()
