import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram import types

import dotenv
from os import getenv
import json
from typing import Dict, Any

import time


from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage


class JSONConfig:
    def __init__(self, config_path: str) -> None:
        self.path = config_path

    def _get_scheme(self) -> Dict[str, Any]:
        with open(self.path, encoding='utf-8') as file:
            return json.load(file)

    def _save_scheme(self, data: dict) -> None:
        with open(self.path, 'w', encoding='utf-8') as file:
            return json.dump(data, file, indent=4, ensure_ascii=False)

    def _get_pretty_path(self, path: str) -> str:
        path = ".".join([f"'{key}'" for key in path.split('.')])
        path = f"[{path.replace('.', '][')}]"

        return path

    def set_value(self, path: str, value: Any) -> None:
        data = self._get_scheme()
        exec(f"data{self._get_pretty_path(path)} = {value}")
        self._save_scheme(data)

    def get_value(self, path: str) -> Dict[str, Any]:
        return eval(f"{self._get_scheme()}{self._get_pretty_path(path)}")


class Config(JSONConfig):
    def get_admins(self):
        return self.get_value('adminId')

    def add_admin(self, admin):
        admins = self.get_admins()
        admins.append(admin)
        self.set_value('adminId', admins)

    def get_channels(self):
        return self.get_value('channels')

    def add_channel(self, channel):
        channels = self.get_channels()
        channels.append(channel)
        self.set_value('channels', channels)

    def delete_channel(self, id):
        channels = self.get_channels()
        d = 0
        for i in channels:
            if int(i["id"]) == int(id):
                channels.pop(d)
            else:
                d += 1
        self.set_value('channels', channels)


dotenv.load_dotenv()
API_TOKEN = getenv('BOT_TOKEN')
storage = MemoryStorage()

json_config = Config('./config.json')

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=storage)


def get_buttons():
    buttons = []
    for i in json_config.get_channels():
        buttons.append([
            InlineKeyboardButton(
                text=i["title"], callback_data=f'chose_{i["id"]}')
        ])
    return buttons


menu_buttons = [
    [InlineKeyboardButton(text='Каналы', callback_data='seeAllChannels')],
    [InlineKeyboardButton(text='Добавить канал', callback_data='addChannel')]
]


def get_buttons_channel(id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сгенерировать ссылку",
                              callback_data=f'generateLink_{id}')],
        [InlineKeyboardButton(text="Удалить канал",
                              callback_data=f'delete_{id}')]
    ])


@dp.message_handler(commands=['restart'], state='*')
async def send_restart(message: types.Message, state: FSMContext):
    if message.from_user.id in json_config.get_admins():
        await state.reset_state()
        await message.answer("admin menu", reply_markup=InlineKeyboardMarkup(inline_keyboard=menu_buttons))


@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    if message.from_user.id in json_config.get_admins():
        await message.answer("admin menu", reply_markup=InlineKeyboardMarkup(inline_keyboard=menu_buttons))


def check_sub_chanell(chat_member):
    if chat_member['status'] == 'administrator':
        return True
    else:
        return False


@dp.callback_query_handler(lambda call: call.data == 'seeAllChannels')
async def callback(call: types.CallbackQuery):
    await call.answer('')

    
    if len(json_config.get_channels()) != 0:
            await call.message.edit_text(
                'Список каналов',
                reply_markup=InlineKeyboardMarkup(row_width=1).add(
                    *[InlineKeyboardButton(channel['title'], callback_data=f'generateLink_{channel["id"]}') 
                    for channel in json_config.get_channels()]
                )
            )
    else:
        await call.message.answer(text='У вас пока еще нет каналов', reply_markup=InlineKeyboardMarkup(inline_keyboard=[menu_buttons[1]]))


@ dp.callback_query_handler(lambda call: call.data.split('_')[0] == 'generateLink')
async def callback(call):
    await call.answer('')

    id = call.data.split('_')[1]
    link = await bot.create_chat_invite_link(chat_id=id, member_limit=1, expire_date=int(time.time()) + 604800)
    await call.message.edit_text(f'''
{link.invite_link} — ваша пригласительная ссылка в VIP. Ссылка одноразовая и после вступления VIP канал отобразиться у вас в чатах. Приятного пользования 🙏
    ''')

    await call.message.answer(
        'Список каналов',
        reply_markup=InlineKeyboardMarkup(row_width=1).add(
            *[InlineKeyboardButton(channel['title'], callback_data=f'generateLink_{channel["id"]}') 
            for channel in json_config.get_channels()]
        )
    )


@ dp.callback_query_handler(lambda call: call.data.split('_')[0] == 'delete')
async def callback(call):
    await call.answer('')

    id = call.data.split('_')[1]
    await call.message.edit_text("Канал удален")

    json_config.delete_channel(id)


class FSMchannel(StatesGroup):
    id = State()
    url = State()


@ dp.callback_query_handler(lambda call: call.data == 'addChannel', state=None)
async def ch_start(call):
    await call.answer('')

    if call.message.chat.id in json_config.get_admins():
        await FSMchannel.id.set()
        await call.message.answer('Перешлите пост канала\n!!!Бот должен быть администратором в канале!!!', reply_markup=ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, keyboard=[[KeyboardButton(text='/restart')]]))


@ dp.message_handler(content_types=types.ContentType.ANY, state=FSMchannel.id)
async def ch_id(message: types.Message, state: FSMContext):
    print('suk')
    if message.forward_from_chat != None:
        bot_id = await bot.get_me()
        try:
            print(message.forward_from_chat)
            if check_sub_chanell(await bot.get_chat_member(chat_id=message.forward_from_chat.id, user_id=bot_id.id)):
                json_config.add_channel(
                    {"id": message.forward_from_chat.id, "title": message.forward_from_chat.title})
                await state.finish()
                await message.answer('Канал добавлен')
                await message.answer("admin menu", reply_markup=InlineKeyboardMarkup(inline_keyboard=menu_buttons))
            else:
                await message.answer('Бот не является администратором канала')
        except:
            await message.answer('Бот не является администратором канала')
    else:
        await message.answer('Перешлите сообщение из кнала')

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
