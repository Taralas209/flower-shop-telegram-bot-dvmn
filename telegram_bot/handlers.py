from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import CallbackContext, ConversationHandler
from .bot_actions import send_number_to_florist, send_order_to_courier
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from datetime import datetime
from .models import Flower, Florist, Courier, Consultation, Order
import os


CHOOSE_OCCASION, CUSTOM_OCCASION_TEXT, CHOOSE_BUDGET, BUTTON_HANDLING, ORDER_FLOWER, CHOOSE_NAME, CHOOSE_SURNAME, CHOOSE_ADDRESS, CHOOSE_DATE, CHOOSE_TIME, CONSULTING, GETTING_NUMBER, CREATE_ORDER = range(13)


def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("День рождения", callback_data='birthday')],
        [InlineKeyboardButton("Свадьба", callback_data='wedding')],
        [InlineKeyboardButton("В школу", callback_data='school')],
        [InlineKeyboardButton("Без повода", callback_data='no_reason')],
        [InlineKeyboardButton("Другой", callback_data='other')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        update.message.reply_text("Привет! К какому событию готовимся? Выберите один из вариантов, либо укажите свой:",
                              reply_markup=reply_markup)
    else:
        update.callback_query.message.reply_text("Привет! К какому событию готовимся? Выберите один из вариантов, либо укажите свой:",
                              reply_markup=reply_markup)
    return CHOOSE_OCCASION


def restart(update, context):
    if update.message:
        update.message.reply_text("Бот перезапущен!")
    else:
        update.callback_query.message.reply_text("Бот перезапущен!")
    context.user_data.clear()
    return start(update, context)


def choose_occasion(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    occasion = query.data

    if occasion == "other":
        query.message.reply_text("Введите повод:")
        return CUSTOM_OCCASION_TEXT
    else:
        context.user_data["occasion"] = occasion
        keyboard = [
            [InlineKeyboardButton("500", callback_data='500')],
            [InlineKeyboardButton("1000", callback_data='1000')],
            [InlineKeyboardButton("2000", callback_data='2000')],
            [InlineKeyboardButton("Больше", callback_data='more')],
            [InlineKeyboardButton("Не важно", callback_data='no_matter')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text("Выберите бюджет:", reply_markup=reply_markup)

    return CHOOSE_BUDGET


def show_budget_buttons(update: Update, _: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("500", callback_data='500')],
        [InlineKeyboardButton("1000", callback_data='1000')],
        [InlineKeyboardButton("2000", callback_data='2000')],
        [InlineKeyboardButton("Больше", callback_data='more')],
        [InlineKeyboardButton("Не важно", callback_data='no_matter')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Выберите бюджет:", reply_markup=reply_markup)


def custom_occasion_text(update: Update, context: CallbackContext):
    user_input = update.message.text
    context.user_data['custom_occasion'] = user_input

    update.message.reply_text(f"Какой другой повод: {user_input}")
    show_budget_buttons(update, context)
    return CHOOSE_BUDGET


def choose_budget(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    context.user_data["budget"] = query.data

    show_flower_and_buttons(update, context)
    return BUTTON_HANDLING


def show_flower_and_buttons(update: Update, context: CallbackContext):
    if context.user_data.get("custom_occasion"):
        occasion = None
    else:
        occasion = context.user_data["occasion"]
    approx_price = context.user_data["budget"]

    flowers = get_filtered_flowers(occasion, approx_price)
    if not flowers:
        print("\nNo flowers found!\n")
        keyboard = [
            [InlineKeyboardButton("Показать всю коллекцию", callback_data='collection')],
            [InlineKeyboardButton("Начать сначала", callback_data='restart')]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        update.callback_query.message.reply_text("Нет подходящих букетов", reply_markup=reply_markup)
        return BUTTON_HANDLING

    if len(flowers) == 1:
        update.callback_query.message.reply_text(f"Нашёлся {len(flowers)} букет")
    context.user_data["flowers"] = flowers
    context.user_data["current_flower_index"] = 0

    send_flower_info(update, context)


def send_flower_info(update, context):
    flowers = context.user_data["flowers"]
    index = context.user_data["current_flower_index"]

    flower = flowers[index]
    print(f"flower = {flower}")

    fs = FileSystemStorage()
    image_path = fs.url(flower.image.name)
    image_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), image_path.lstrip('/'))

    flower_description = (
        f"Название: {flower.name}\n"
        f"Описание: {flower.description}\n"
        f"Цена: {flower.price} руб."
    )
    catalogue_message = update.callback_query.message.reply_photo(photo=open(image_path, 'rb'), caption=flower_description)
    keyboard = [
        [InlineKeyboardButton("Назад", callback_data='back'), InlineKeyboardButton("Вперёд", callback_data='forward')],
        [InlineKeyboardButton("Заказать", callback_data='order')],

    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.callback_query.message.reply_text(text="Посмотрите другие букеты или сделайте заказ", reply_markup=reply_markup)

    keyboard2 = [
        [InlineKeyboardButton("Заказать консультацию", callback_data='consulting')],
        [InlineKeyboardButton("Посмотреть всю коллекцию", callback_data='collection')],

    ]
    reply_markup2 = InlineKeyboardMarkup(keyboard2)
    update.callback_query.message.reply_text(text="Хотите что-то еще более уникальное? Подберите другой букет из нашей коллекции или закажите консультацию флориста",
                                             reply_markup=reply_markup2)

    context.user_data["catalogue_message_id"] = catalogue_message.message_id


def get_filtered_flowers(occasion, approx_price):
    price_range = {
        "500": (500, 600),
        "1000": (1000, 1500),
        "2000": (2000, 3000),
        "more": 3000,
    }
    print(f"\n{occasion} - {approx_price}")
    if occasion:
        flowers_list = Flower.objects.filter(occasion=occasion)
    else:
        flowers_list = Flower.objects.all()

    if approx_price == "more":
        flowers_list = flowers_list.filter(price__gte=price_range[approx_price])
    elif approx_price != "no_matter":
        flowers_list = flowers_list.filter(price__range=price_range[approx_price])

    return flowers_list


def get_all_flowers():
    return Flower.objects.all()


def button_handling(update: Update, context:  CallbackContext):
    query = update.callback_query
    query.answer()

    index = context.user_data.get("current_flower_index")

    if query.data == "order":
        update.callback_query.message.reply_text("Начнем процесс заказа!")
        return ask_name(update, context)
    elif query.data == 'back':
        index = index - 1
        if index < 0:
            index = len(context.user_data["flowers"]) - 1
        context.user_data["current_flower_index"] = index
        return update_catalogue(update, context)
    elif query.data == 'forward':
        index = index + 1
        if index >= len(context.user_data["flowers"]):
            index = 0
        context.user_data["current_flower_index"] = index
        return update_catalogue(update, context)
    elif query.data == 'consulting':
        update.callback_query.message.reply_text("Укажите номер телефона, и наш флорист перезвонит вам в течение 20 минут")
        return get_number_for_consulting(update, context)
    elif query.data == 'collection':
        print("\nПользователь нажал кнопку Коллекция\n")
        update.callback_query.message.reply_text("Вот вся наша коллеция:")
        context.user_data["flowers"] = get_all_flowers()
        context.user_data["current_flower_index"] = 0
        send_flower_info(update, context)
    elif query.data == 'restart':
        print("\nRestart button was pressed\n")
        restart(update, context)


def update_catalogue(update, context):
    query = update.callback_query
    query.answer()
    catalogue_message_id = context.user_data["catalogue_message_id"]

    flowers = context.user_data["flowers"]
    index = context.user_data["current_flower_index"]

    flower = flowers[index]
    fs = FileSystemStorage()
    image_path = fs.url(flower.image.name)
    image_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), image_path.lstrip('/'))

    flower_description = (
        f"Название: {flower.name}\n"
        f"Описание: {flower.description}\n"
        f"Цена: {flower.price} руб."
    )

    with open(image_path, "rb") as new_image:
        new_photo = InputMediaPhoto(
            media=new_image,
            caption=flower_description
        )

        context.bot.edit_message_media(
            message_id=catalogue_message_id,
            chat_id=query.message.chat_id,
            media=new_photo,
        )


def ask_name(update: Update, context: CallbackContext):
    update.callback_query.message.reply_text("Пожалуйста, введите ваше имя:")
    return CHOOSE_SURNAME


def ask_surname(update: Update, context: CallbackContext):
    context.user_data["name"] = update.message.text
    update.message.reply_text("Теперь введите вашу фамилию:")
    return CHOOSE_ADDRESS


def ask_address(update: Update, context: CallbackContext):
    context.user_data["surname"] = update.message.text
    update.message.reply_text("Введите ваш адрес (город, улица и номер дома):")
    return CHOOSE_DATE


def ask_date(update: Update, context: CallbackContext):
    context.user_data["address"] = update.message.text
    update.message.reply_text("Введите дату доставки (дд.мм.гггг):")
    return CHOOSE_TIME


def ask_time(update: Update, context: CallbackContext):
    date_str = update.message.text
    date_obj = datetime.strptime(date_str, "%d.%m.%Y").date()
    context.user_data["date"] = date_obj
    update.message.reply_text("Введите время доставки (чч:мм):")
    return ORDER_FLOWER


def get_order(update: Update, context: CallbackContext):
    context.user_data["time"] = update.message.text
    flowers = context.user_data["flowers"]
    index = context.user_data["current_flower_index"]

    flower = flowers[index]
    order_info = f"""Вот ваш заказ:
Название букета: {flower.name}
Цена букета: {flower.price}
Имя: {context.user_data["name"]}
Фамилия: {context.user_data["surname"]}
Адрес: {context.user_data["address"]}
Дата и время доставки: {context.user_data["date"]} {context.user_data["time"]}"""

    keyboard = [[InlineKeyboardButton("Подтверждаю", callback_data='confirm_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(order_info, reply_markup=reply_markup)
    context.user_data["selected_flower"] = flower

    return CREATE_ORDER


def create_order(update: Update, context: CallbackContext):
    order = Order(
        flower=context.user_data["selected_flower"],
        first_name=context.user_data["name"],
        last_name=context.user_data["surname"],
        address=context.user_data["address"],
        delivery_date=context.user_data["date"],
        delivery_time=context.user_data["time"],
        order_datetime=datetime.now()
    )
    order.save()

    update.callback_query.message.reply_text("Ваш заказ успешно принят, спасибо за доверие!")

    send_order_to_courier(update, context, order)


# def show_collections(update: Update, context: CallbackContext):
#     flower = Flower.objects.order_by('?').first()
#     context.user_data['flower_id'] = flower.id
#
#     fs = FileSystemStorage()
#     image_path = fs.url(flower.image.name)
#     image_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), image_path.lstrip('/'))
#
#     if update.callback_query:
#         message = update.callback_query.message
#     else:
#         message = update.message
#
#     message.reply_photo(photo=open(image_path, 'rb'))
#     message.reply_text(
#         f"Название: {flower.name}\n"
#         f"Описание: {flower.description}\n"
#         f"Цена: {flower.price} руб."
#     )
#     keyboard = [
#         [InlineKeyboardButton("Назад", callback_data='back'), InlineKeyboardButton("Вперёд", callback_data='forward')],
#         [InlineKeyboardButton("Заказать", callback_data='order')],
#     ]
#     reply_markup = InlineKeyboardMarkup(keyboard)
#     message.reply_text(text="Посмотрите другие букеты или сделайте заказ", reply_markup=reply_markup)
#
#     return BUTTON_HANDLING


def get_number_for_consulting(update: Update, context: CallbackContext):
    update.callback_query.message.reply_text("Пожалуйста, введите ваш номер телефона:")
    return GETTING_NUMBER


def get_number_to_florist(update: Update, context: CallbackContext):
    context.user_data["number"] = update.message.text
    update.message.reply_text("Флорист скоро свяжется с вами. А пока можете присмотреть что-нибудь из готовой коллекции")

    consultation = Consultation(
        occasion=context.user_data.get("occasion"),
        budget=context.user_data.get("budget"),
        number=context.user_data.get("number"),
        # created_at=datetime.now()
    )
    consultation.save()

    send_number_to_florist(update, context, consultation)

    update.callback_query.message.reply_text("Вот вся наша коллеция:")
    context.user_data["flowers"] = get_all_flowers()
    send_flower_info(update, context)
