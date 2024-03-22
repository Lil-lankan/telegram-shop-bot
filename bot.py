import logging
import telegram
import telegram.ext
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove #, LabeledPrice, ParseMode
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, PreCheckoutQueryHandler, ConversationHandler, filters
import os
from supabase.client import create_client, Client
import requests
import math
import websockets
from web3 import AsyncWeb3, Web3
import web3.providers.websocket.websocket_v2
from web3.auto import w3
import re

url:str = ""
key:str = ""
supabase:Client = create_client(url, key)

#Database password = 
#email = 
alchemy_key = ''
Websocket_URL = ''
alchemy_url = ''
w3 = Web3(Web3.HTTPProvider(alchemy_url))

logging.basicConfig(format ='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

store_name = ''
bot_token:str = ""
bot = telegram.Bot(token=bot_token)
#crypto_token:str = ""
temp_token = ""
shop_master_id = #your ID
check_in_stock = True
decimal_interval = 0.5
#Commands
global payfail
payfail = False

def get_stock():
    data = supabase.table('stock').select('*').execute().data
    global menustr
    global item_dict
    menustr= ""
    item_dict = {}
    name = ""
    price = 0
    unit = ""
    stock = 0
    for i in data:
        run_count = 0
        for v in i.values():
            run_count +=1
            match run_count:
                case 1:
                    name = v
                    item_dict.update({name:[]})
                case 2:
                    stock = v
                    item_dict[name].append(stock)
                case 3:
                    price = v
                    item_dict[name].append(price)
                case 4:
                    unit = v
                    item_dict[name].append(unit)
                case 5:
                    type = v
                    item_dict[name].append(type)
                    menustr += f"{name:s} - ${price:.2f}/{unit:s}\n"
    return
get_stock()

def get_value(name, property):
    value = None
    match property:
        case 'stock':
            value = item_dict[name][0]
        case 'price':
            value = item_dict[name][1]
        case 'unit':
            value = item_dict[name][2]
        case 'type':
            value = item_dict[name][3]
    return value


def dict_to_str(dict:dict):
    dict_str = ''
    for i in dict:
        unit = get_value(i, 'unit')
        dict_str += f'{str(i)} : {str(dict[i])} {unit}\n'
    return dict_str

def validate_postal(postal):
    count = 0
    valid_postal = True
    if len(postal) == 7:
        for i in postal:
            if i != ' ':
                count += 1
                if count%2!=0:
                    if i.isalpha() == False:
                        validate_postal = False
                else:
                    if i.isdigit() == False:
                        valid_postal = False
            else:
                if count != 3:
                    validate_postal = False
    else:
        valid_postal = False
    return valid_postal


def send_to_telegram(chat_id, text):

    apiURL = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    try:
        response = requests.post(apiURL, json={'chat_id': chat_id, 'text': text})
        print(f'>>><<<>>><<<>>>|{response.text}|>>><<<>>><<<>>>')
    except Exception as e:
        print(f"!!!%%%$$$???!!!%%%$$$???|{e}|!!!%%%$$$???!!!%%%$$$???")

def check_payment():
    return True

async def ethtest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    block = str(w3.eth.get_block('latest'))
    chat_id:int = 0
    if update.message is not None:
        chat_id = update.message.chat.id
    await context.bot.send_message(chat_id, text=block)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id:int = 0
    if update.message is not None:
        chat_id = update.message.chat.id
    await context.bot.send_message(chat_id, text=f"Welcome to {store_name}. to see a list of commands, type \"/help\"")

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id:int = 0
    if update.message is not None:
        chat_id = update.message.chat.id
        #stock_lst.{name:s}
    await context.bot.send_message(chat_id, text=f'{menustr}')

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id:int = 0
    if update.message is not None:
        chat_id = update.message.chat.id
    await context.bot.send_message(chat_id, text="Commands:\n /menu - see menu\n /order - place an order")

async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = 0
    if update.message is not None:
        chat_id = update.message.chat.id
        await context.bot.send_message(chat_id, text=str(chat_id))

#Order handling
CHOOSING, ADDING, REMOVING, CONFIRM, PAY, ADDRESS, VERIFICATION, PAYFAIL = range(8)
reply_keyboard = [['add item', 'remove item','show cart', 'done', 'cancel']]
markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

async def order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_stock
    global order_dict
    current_stock = {}
    order_dict = {}
    if update.message is not None:
        await update.message.reply_text('Choose options below, press \'done\' to confirm cart when order is finished',reply_markup = markup)
    return CHOOSING

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is not None:
        await update.message.reply_text('Enter your choice as \'item:quantity\', with quantity as a number without unit:')
    return ADDING

async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is not None:
        await update.message.reply_text('Enter the name of the item you want to remove:')
    return REMOVING

async def adding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if  update.message is not None and update.message.text is not None:
        text = update.message.text
        entry = text.lower().split(':')
        if entry!=[text]:
            if entry[0] in item_dict.keys():
                try:
                    float(entry[1])
                    quant = float(entry[1]).is_integer() and int(entry[1]) or float(entry[1])
                    stock = get_value(entry[0], 'type') == 'int' and int(get_value(entry[0], 'stock')) or float(get_value(entry[0], 'stock'))
                    if ((quant-math.floor(quant))%decimal_interval).is_integer():
                        if check_in_stock == True and float(entry[1]) > stock:
                            await update.message.reply_text(f'Unable to add to cart. maximum quantity of {entry[0]} is {stock}', reply_markup=markup)
                        else:
                            quant = entry[1].isdigit() and int(entry[1]) or float(entry[1])
                            order_dict.update({entry[0]:quant})
                            current_stock.update({entry[0]:(stock-quant)})
                            await update.message.reply_text(f'{entry[0]} added to cart.', reply_markup=markup)
                    else:
                        await update.message.reply_text(f'Entered quantity is not valid (decimal must be a multiple of {decimal_interval})', reply_markup=markup)
                except ValueError:
                    await update.message.reply_text(f'Entered quantity is not a number.', reply_markup=markup)
            else:
                await update.message.reply_text(f'{entry[0]} is unavailable or out of stock, please select a new action.', reply_markup=markup)
        else:
            await update.message.reply_text('Incorrect format (should be itemName:quantity).', reply_markup=markup)
    return CHOOSING

async def removing(update: Update, context = ContextTypes.DEFAULT_TYPE):
    if  update.message is not None and update.message.text is not None:
        text = update.message.text
        entry = text.lower()
        if entry in list(order_dict.keys()):
            order_dict.pop(entry)
            del current_stock[entry]
            await update.message.reply_text(f'{entry} removed from cart.', reply_markup=markup)
        else:
            await update.message.reply_text(f'{entry} is not in cart.', reply_markup=markup)
    return CHOOSING

async def show_cart(update: Update, context = ContextTypes.DEFAULT_TYPE):
    if update.message is not None:
        if order_dict != {}:
            cart = dict_to_str(order_dict)
            await update.message.reply_text(f'{cart}', reply_markup=markup)
        else:
            await update.message.reply_text(f'Cart is empty.', reply_markup=markup)
    return CHOOSING

async def go_back(update: Update, context = ContextTypes.DEFAULT_TYPE):
    if update.message is not None:
        await update.message.reply_text('Choose options below, press \'done\' to confirm cart when order is finished',reply_markup = markup)
    return CHOOSING

async def get_addy(update: Update, context = ContextTypes.DEFAULT_TYPE):
    if update.message is not None:
        await update.message.reply_text('enter address for delivery as \'address, postal code (LNL NLN)\':')
    return ADDRESS

async def pay(update: Update, context = ContextTypes.DEFAULT_TYPE):
    pay_keyboard = [['done']]
    pay_markup = ReplyKeyboardMarkup(pay_keyboard, one_time_keyboard=True)
    global addy
    if update.message is not None and update.message.text is not None:
        text = update.message.text
        entry = text.lower().split(', ')
        if text == 'try again':
            await update.message.reply_text(f'Send eth to this token: {temp_token}\nenter \'done\' when complete and wait for verification', reply_markup=pay_markup)
            return VERIFICATION
        try:
            if validate_postal(entry[1]) == True:
                addy = entry
                await update.message.reply_text(f'Send eth to this token: {temp_token}\nenter \'done\' when complete and wait for verification', reply_markup=pay_markup)
                return VERIFICATION
            else:
                await update.message.reply_text('Your postal code is invalid, enter as \'LNL NLN\'', reply_markup=confirm_markup)
                return CONFIRM
        except IndexError:
            await update.message.reply_text('The address you entered is in the wrong format. please use \"adress, postal code\"\n postal code must be in form \"LNL NLN\"')
            return CONFIRM

async def confirm(update: Update, context = ContextTypes.DEFAULT_TYPE):
    confirm_keyboard = [['continue', 'go back']]
    global confirm_markup
    confirm_markup = ReplyKeyboardMarkup(confirm_keyboard, one_time_keyboard=True)
    if update.message is not None:
        if order_dict != {}:
            total = 0
            for i in order_dict:
                total += get_value(i, 'price')*order_dict[i]
            cart = dict_to_str(order_dict)
            await update.message.reply_text(f'final cart is:\n{cart}\n total price is {total}\nshipping adress is: {addy[0]}, {addy[1]}', reply_markup=confirm_markup)
        else:
            await update.message.reply_text(f'Cart is empty.', reply_markup=markup)
    return CONFIRM

async def verify(update: Update, context = ContextTypes.DEFAULT_TYPE):
    payfail = False
    payfail_keyboard = [['try again', 'cancel']]
    payfail_markup = ReplyKeyboardMarkup(payfail_keyboard, one_time_keyboard=True)
    if update.message is not None:
        if check_payment():
            send_to_telegram(shop_master_id, f'New order:\n{dict_to_str(order_dict)}\nSend to:\n{addy[0]}, {addy[1]}')
            for i in current_stock:
                data, count = supabase.table('stock').update({'count': (get_value(i, 'stock')-current_stock[i])}).eq('name', i).execute()
                await update.message.reply_text(f'Payment recieved. Your order has been placed.\nThank you for shopping with {store_name}')
            return ConversationHandler.END
        else:
            payfail = True
            await update.message.reply_text('Payment could not be verified.', reply_markup=payfail_markup)
            return PAYFAIL


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is not None:
       await update.message.reply_text('You\'ve cancelled you order. you can restart it by entering \'/order\'', reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

    #await context.bot.send_message(chat_id, text=f"Send eth to this address: {crypto_token:s}")
order_handler = ConversationHandler(
            entry_points=[CommandHandler("order", order)],
            states={
                CHOOSING: [
                                MessageHandler(filters.Regex("^add item$"), add),
                                MessageHandler(filters.Regex("^remove item$"), remove),
                                MessageHandler(filters.Regex("^show cart$"), show_cart),
                                MessageHandler(filters.Regex("^done$"), confirm)
                          ],
                ADDING: [
                            MessageHandler(filters.TEXT & ~(filters.COMMAND), adding)
                        ],
                REMOVING: [
                            MessageHandler(filters.TEXT & ~ (filters.COMMAND), removing)
                          ],
                CONFIRM: [
                            MessageHandler(filters.Regex("^continue$"), get_addy),
                            MessageHandler(filters.Regex("^go back$"), go_back)
                         ],
                ADDRESS: [
                            MessageHandler(filters.TEXT & ~ (filters.COMMAND), pay)
                         ],
                VERIFICATION: [
                                MessageHandler(filters.Regex("^done$"), verify)
                              ],
                PAYFAIL: [
                                MessageHandler(filters.Regex("try again"), pay)
                         ]
                   },
            fallbacks=[MessageHandler(filters.Regex("^cancel$"), cancel)]
        )

if __name__ == '__main__':
    bot = ApplicationBuilder().token(bot_token).build()
    #Handlers
    start_handler = CommandHandler('start', start)
    menu_handler = CommandHandler('menu', menu)
    help_handler = CommandHandler('help', help)
    id_handler = CommandHandler('get_id', get_id)
    ethtest_handler = CommandHandler('ethtest', ethtest)
    bot.add_handler(start_handler)
    bot.add_handler(menu_handler)
    bot.add_handler(order_handler)
    bot.add_handler(help_handler)
    bot.add_handler(id_handler)
    bot.add_handler(ethtest_handler)

    bot.run_polling()