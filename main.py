import asyncio
import csv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types.input_file import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database
from config import BOT_TOKEN, ADMIN_ID

# from dotenv import load_dotenv
# load_dotenv()
# BOT_TOKEN = os.getenv("BOT_TOKEN")
# ADMIN_ID = int(os.getenv("ADMIN_ID", 0))


# print("Loaded BOT_TOKEN:", BOT_TOKEN)

# BOT_TOKEN = ""
# ADMIN_ID = 0

# with open(".env", "r") as f:
#     lines = f.readlines()
#     for line in lines:
#         if line.startswith("BOT_TOKEN="):
#             BOT_TOKEN = line.strip().split("=", 1)[1]
#         elif line.startswith("ADMIN_ID="):
#             ADMIN_ID = int(line.strip().split("=", 1)[1])

# print("Loaded BOT_TOKEN:", BOT_TOKEN)
# print("repr:", repr(BOT_TOKEN))
# print("Colon check:", ':' in BOT_TOKEN)
# print("Token bytes:", [hex(ord(c)) for c in BOT_TOKEN])


if not BOT_TOKEN:
    raise ValueError("Не указан токен бота в переменной окружения BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class AddManagerStates(StatesGroup):
    name = State()
    photo = State()

class CommentState(StatesGroup):
    waiting = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    managers = await database.get_managers()
    if not managers:
        await message.answer("Пока нет доступных менеджеров для оценки.")
        return
    for manager in managers:
        manager_id, name, photo_id, _, _ = manager
        builder = InlineKeyboardBuilder()
        builder.button(text=f"Оценить {name}", callback_data=f"rate_{manager_id}")
        builder.adjust(1)
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=photo_id,
            caption=f"{name}",
            reply_markup=builder.as_markup()
        )

@dp.callback_query(F.data.startswith("rate_"))
async def choose_manager(callback: types.CallbackQuery):
    manager_id = int(callback.data.split("_")[1])
    managers = await database.get_managers()
    name = next((m[1] for m in managers if m[0] == manager_id), "неизвестный")
    builder = InlineKeyboardBuilder()
    for stars in range(1, 6):
        builder.button(text=f"{stars} ⭐", callback_data=f"star_{manager_id}_{stars}")
    builder.adjust(5)
    await callback.message.answer(f"Вы оцениваете менеджера {name}. Пожалуйста, выберите количество звезд:", reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("star_"))
async def choose_stars(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    manager_id = int(parts[1])
    stars = int(parts[2])
    rating_id = await database.add_rating(manager_id, stars)
    builder = InlineKeyboardBuilder()
    builder.button(text="Да", callback_data=f"comment_yes_{rating_id}")
    builder.button(text="Нет", callback_data=f"comment_no_{rating_id}")
    builder.adjust(2)
    await callback.message.answer("Хотите оставить комментарий?", reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("comment_yes_"))
async def ask_comment(callback: types.CallbackQuery, state: FSMContext):
    rating_id = int(callback.data.split("_")[2])
    await state.update_data(rating_id=rating_id)
    await state.set_state(CommentState.waiting)
    await callback.message.answer("Пожалуйста, введите ваш комментарий:")
    await callback.answer()

@dp.callback_query(F.data.startswith("comment_no_"))
async def no_comment(callback: types.CallbackQuery):
    await callback.message.answer("Спасибо за ваш отзыв!")
    await callback.answer()

@dp.message(CommentState.waiting)
async def process_comment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    rating_id = data.get("rating_id")
    comment = message.text
    if rating_id:
        await database.update_rating_comment(rating_id, comment)
    await message.answer("Спасибо за ваш отзыв!")
    await state.clear()

async def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

@dp.message(Command("panel"))
async def admin_panel(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к этой команде.")
        return
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin_stat")
    builder.button(text="➕ Добавить менеджера", callback_data="admin_add")
    builder.button(text="📁 Экспортировать рейтинги", callback_data="admin_export")
    builder.button(text="🗑️ Удалить менеджера", callback_data="admin_delete")
    builder.adjust(2)
    await message.answer("Панель администратора:", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "admin_stat")
async def show_statistics(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    managers = await database.get_managers()
    if not managers:
        await callback.message.answer("Нет менеджеров в базе данных.")
    else:
        text = "Статистика менеджеров:"
        for _, name, _, rating, total_votes in managers:
            text += f"\n\n{name}: {rating:.2f} ⭐ ({total_votes} голосов)"
        await callback.message.answer(text)
    await callback.answer()

@dp.callback_query(F.data == "admin_add")
async def add_manager_start(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(AddManagerStates.name)
    await callback.message.answer("Введите имя нового менеджера:")
    await callback.answer()

@dp.message(AddManagerStates.name)
async def add_manager_name(message: types.Message, state: FSMContext):
    name = message.text
    await state.update_data(manager_name=name)
    await state.set_state(AddManagerStates.photo)
    await message.answer("Отлично! Теперь отправьте фотографию менеджера:")

@dp.message(AddManagerStates.photo, F.photo)
async def add_manager_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    name = data.get("manager_name")
    photo = message.photo[-1]
    photo_id = photo.file_id
    await database.add_manager(name, photo_id)
    await message.answer(f"Менеджер \"{name}\" добавлен в систему.")
    await state.clear()

@dp.callback_query(F.data == "admin_export")
async def export_ratings(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    ratings = await database.get_all_ratings()
    if not ratings:
        await callback.message.answer("Нет оценок для экспорта.")
        await callback.answer()
        return

    filename = "ratings.csv"
    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["id", "manager_id", "stars", "comment", "timestamp"])
        for row in ratings:
            writer.writerow(row)

    await bot.send_document(callback.from_user.id, FSInputFile(path=filename))
    await callback.answer()

@dp.callback_query(F.data == "admin_delete")
async def delete_manager_list(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    managers = await database.get_managers()
    if not managers:
        await callback.message.answer("Нет менеджеров для удаления.")
        await callback.answer()
        return
    builder = InlineKeyboardBuilder()
    for m in managers:
        manager_id, name, _, _, _ = m
        builder.button(text=name, callback_data=f"delete_{manager_id}")
    builder.adjust(1)
    await callback.message.answer("Выберите менеджера для удаления:", reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("delete_"))
async def delete_manager_callback(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    manager_id = int(callback.data.split("_")[1])
    await database.delete_manager(manager_id)
    await callback.message.answer("Менеджер удален.")
    await callback.answer()

async def main():
    await database.init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Exit')
