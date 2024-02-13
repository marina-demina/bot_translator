import os
import logging
import logging.config

import environ
import aiogram.utils.markdown as md
from aiogram import Bot, Dispatcher, types, BaseMiddleware
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from tools import get_translate_ru_to_en, get_translate_en_to_ru
from config import translator_bot_token

env = environ.Env()
environ.Env.read_env()

logging.config.fileConfig('logging.ini', disable_existing_loggers=False)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get(translator_bot_token)


bot_translator = Bot(token=translator_bot_token)
storage = MemoryStorage()
dp = Dispatcher(bot_translator, storage=storage)

dp.middleware.setup(BaseMiddleware())


class Form(StatesGroup):
    first_choice = State()
    language_choice = State()
    text_to_translate = State()


@dp.message_handler(state='*', commands='start')
async def send_welcome(message: types.Message):
    user = message.from_user.first_name

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    markup.add('Нужно кое-что перевести')
    markup.add('/help')

    await Form.first_choice.set()
    await message.answer(
        f'Привет, {user}!\nЯ - бот-переводчик\n'
                'Чем могу помочь?\nСписок доступных команд /help',
        reply_markup=markup
    )


@dp.message_handler(state='*', commands='help')
async def help_handler(message: types.Message, state: FSMContext):

    await bot_translator.send_message(
        message.chat.id,
        md.text(
            md.text('/start- запуск Бота'),
            md.text('/help - список команд'),
            md.text('/cancel - отменить выбор'),
            md.text('/translate - начать перевод'),
            sep='\n'
        ),
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.finish()


@dp.message_handler(state='*', commands='cancel')
async def cancel_handler(message: types.Message, state: FSMContext):

    current_state = await state.get_state()
    if current_state is None:
        return await bot_translator.send_message(
            message.chat.id, 'Начать сначала /start, /help')

    await state.finish()
    await message.answer('Начать сначала /start, /help',
                         reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler(
    lambda message:
    message.text not in ['Нужно кое-что перевести'],
    state=Form.first_choice
)
async def process_first_choice_invalid(message: types.Message):
    return await message.answer('Не понятно')


@dp.message_handler(state='*', commands='translate')
@dp.message_handler(lambda message: message.text == 'Нужно кое-что перевести.',
                    state=Form.first_choice)
async def choice_translation_language(message: types.Message,
                                      state: FSMContext):
    await state.update_data(first_choice=message.text)

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    markup.add('русский >> английский')
    markup.add('английский >> русский')
    markup.add('/help')

    await state.finish()
    await Form.language_choice.set()
    await message.answer('Выбери язык.', reply_markup=markup)


@dp.message_handler(
    lambda message:
    message.text not in ['русский >> английский', 'английский >> русский'],
    state=Form.language_choice
)
async def process_language_choice_invalid(message: types.Message):
    return await message.answer('Не понятно :face_with_monocle:')


@dp.message_handler(
    lambda message:
    message.text == 'русский >> английский' or 'английский >> русский',
    state=Form.language_choice)
async def process_translate(message: types.Message, state: FSMContext):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    markup.add('/help')
    markup.add('/translate')
    await state.update_data(language_choice=message.text)
    async with state.proxy() as data:
        data['language'] = message.text

    await Form.text_to_translate.set()
    await message.answer('Введи текст.', reply_markup=markup)


@dp.message_handler(state=Form.text_to_translate)
async def send_translate_text(message: types.Message, state: FSMContext):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    markup.add('/help')
    markup.add('/translate')
    async with state.proxy() as data:
        data['text'] = message.text

    if data['language'] == 'русский >> английский':
        translated_text = get_translate_ru_to_en(data['text'])
    else:
        translated_text = get_translate_en_to_ru(data['text'])

    await message.answer(translated_text, reply_markup=markup)


@dp.message_handler()
async def process_message_out_of_state(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    markup.add('/help')
    markup.add('/translate')
    await message.answer(reply_markup=markup)


async def main():
    await dp.start_polling(bot_translator)