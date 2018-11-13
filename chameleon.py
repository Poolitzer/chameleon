# space.libraries
import json
import logging
import random
import re
from telegram import InlineKeyboardMarkup, ParseMode, ForceReply
from telegram.ext import CommandHandler, Updater, Filters, MessageHandler, ConversationHandler
from telegram.ext.callbackqueryhandler import CallbackQueryHandler
from telegram.inline.inlinekeyboardbutton import InlineKeyboardButton
from telegram.utils import helpers
from telegram.error import Unauthorized
from pymongo import MongoClient

logging.basicConfig(format='%(asctime)s - %(first_name)s - %(levelname)s - %(message)s', level=logging.INFO)
LANGUAGE, STRING, UPDATE, ACCEPT = range(4)

data_base = open('./language.json')
lang = json.load(data_base)


class Source:
    def __init__(self):
        data_file = open('./list.json')
        data = json.load(data_file)
        self.topic = random.choice(data["standard"])
        all_words = data[self.topic]
        self.word_list = self.topic + ": " + "\n"
        for x in range(0, len(all_words)):
            self.word_list += str(all_words[x]) + ", "
        self.secret_word = random.choice(data[self.topic])


class GlobalVariables:
    game_running = False
    gamers = []
    messages = []
    chameleon = None
    chatid = None
    shuffle = []
    words = []
    voted = []
    stringcode = None
    string = None
    votelist = {}

    def game_status(self, status):
        self.game_running = status

    def message_add(self, message):
        self.messages.append(message)

    def message_del(self):
        self.messages = []

    def gamers_add(self, gamer):
        self.gamers.append(gamer)

    def gamers_rem(self, gamer):
        self.gamers.remove(gamer)

    def gamers_del(self):
        self.gamers = []

    def gamer_list(self):
        temp = []
        for gamer in self.gamers:
            temp.append(helpers.mention_html(gamer.id, gamer.name))
        return temp

    def choose_chameleon(self, chameleon):
        self.chameleon = chameleon

    def shuffle_save(self, order):
        self.shuffle = order

    def words_add(self, word):
        self.words.append(word)

    def voted_add(self, voter):
        self.voted.append(voter)

    def stringcode_save(self, stringy):
        self.stringcode = stringy

    def string_save(self, stringy):
        self.string = stringy

    def votelist_create(self):
        temp = []
        for gamer in self.gamers:
            self.votelist[gamer.name] = 0
            temp.append(helpers.mention_html(gamer.id, gamer.name))
        return temp

    def votelist_update(self, gamers):
        self.votelist[gamers] += 1
        temp = []
        for key, value in self.votelist.items():
            for gamer in self.gamers:
                if key == gamer.name:
                    temp.append([helpers.mention_html(gamer.id, gamer.name), value])
        return temp


class Buttons:
    @staticmethod
    def join_button(langcode):
        temp = [[InlineKeyboardButton(lang["start_game_buttons"][langcode][0], callback_data="joining"),
                 InlineKeyboardButton(lang["start_game_buttons"][langcode][1], callback_data="leaving")]]
        return InlineKeyboardMarkup(temp)

    secret_button = InlineKeyboardMarkup([[InlineKeyboardButton("Show secret word", callback_data="secret word")]])
    string_buttons = InlineKeyboardMarkup([[InlineKeyboardButton("Accept", callback_data="stringyes"),
                                            InlineKeyboardButton("Decline", callback_data="stringno")]])

    @staticmethod
    def vote():
        temp = []
        subtemp = []
        x = 0
        for gamer in GlobalVariables.gamers:
            subtemp.append(InlineKeyboardButton(gamer.name, callback_data="vote{}".format(gamer.id)))
            x += 1
            if x is 2:
                temp.append(subtemp)
                subtemp = []
                x = 0
            elif gamer is GlobalVariables.gamers[-1] and x is 1:
                temp.append(subtemp)
        return InlineKeyboardMarkup(temp)

    @staticmethod
    def languages():
        langtemp = []
        temp = []
        subtemp = []
        x = 0
        for languages, dict_ in lang["start_game"].items():
            langtemp.append(languages)
        for languages in langtemp:
            subtemp.append(InlineKeyboardButton(languages, callback_data="lang{}".format(languages)))
            x += 1
            if x is 2:
                temp.append(subtemp)
                subtemp = []
                x = 0
            elif languages is langtemp[-1] and x is 1:
                subtemp.append(InlineKeyboardButton("Add a new one", callback_data="langadd"))
                temp.append(subtemp)
        if x == 0:
            temp.append([InlineKeyboardButton("Add a new one", callback_data="langadd")])
        return InlineKeyboardMarkup(temp)

    @staticmethod
    def updatelang(langcode):
        stringtemp = []
        temp = []
        subtemp = []
        x = 0
        for languages, dict_ in lang.items():
            stringtemp.append(languages)
        for strings in stringtemp:
            subtemp.append(InlineKeyboardButton(strings, callback_data="string{}{}".format(langcode, strings)))
            x += 1
            if x is 2:
                temp.append(subtemp)
                subtemp = []
                x = 0
            elif strings is stringtemp[-1] and x is 1:
                temp.append(subtemp)
        return InlineKeyboardMarkup(temp)

    @staticmethod
    def start(user_id, chat_id):
        return InlineKeyboardMarkup([[InlineKeyboardButton("Start", "https://t.me/TheChameleonBot?start={}|{}"
                                                           .format(user_id, chat_id))]])

    @staticmethod
    def config(chat_id):
        temp = [[InlineKeyboardButton("Change language", callback_data="changelg|{}".format(chat_id))]]
        return InlineKeyboardMarkup(temp)

    @staticmethod
    def language(chat_id):
        langtemp = []
        temp = []
        subtemp = []
        x = 0
        for languages, dict_ in lang["start_game"].items():
            langtemp.append(languages)
        for languages in langtemp:
            subtemp.append(InlineKeyboardButton(languages, callback_data="updatelang{}|{}".format(languages, chat_id)))
            x += 1
            if x is 2:
                temp.append(subtemp)
                subtemp = []
                x = 0
            elif languages is langtemp[-1] and x is 1:
                temp.append(subtemp)
        return InlineKeyboardMarkup(temp)


class Gamers:
    def __init__(self, user_id, username):
        self.score = 0
        self.id = user_id
        self.name = username
        self.vote = False
        self.lang = "en"
        self.translator = False


class Group:
    def __init__(self, group_id):
        self.id = group_id
        self.lang = "en"


class Database:

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Database init")
        self.db = MongoClient()
        self.db = self.db["chameleon"]

    def insertgamer(self, gamer):
        self.db.gamers.insert_one(gamer)

    def insertgroup(self, group):
        self.db.groups.insert_one(group)

    def find_entry(self, collection, ids, username=None):
        temp = self.db[collection].find_one({"id": ids})
        if not temp:
            if collection == "users":
                self.insertgamer(vars(Gamers(ids, username)))
            else:
                self.insertgroup(vars(Group(ids)))
            return "en"
        else:
            return temp["lang"]

    def update_entry_language(self, collection, ids, langcode):
        return self.db[collection].update_one({"id": ids}, {'$set': {'lang': langcode}})

    def update_entry_translator(self, ids, langcode):
        return self.db["users"].update_one({"id": ids}, {'$set': {'translator': langcode}})


def create_mention(user):
    return helpers.mention_html(user[0], user[1])


Database = Database()
GlobalVariables = GlobalVariables()
theSource = Source()
Buttons = Buttons()


def start(bot, update, job_queue):
    langcode = Database.find_entry("groups", update.effective_chat.id)
    if not GlobalVariables.game_running:
        message = bot.send_message(chat_id=update.message.chat_id, text=lang["start_game"][langcode],
                                   reply_markup=Buttons.join_button(langcode))
        GlobalVariables.message_add(message)
        job_queue.run_repeating(reminder, 20, context=update.message.chat_id)
    else:
        bot.send_message(update.message.chat_id, lang["start_game_already_running"][langcode],
                         reply_markup=Buttons.join_button(langcode))


def reminder(bot, job):
    langcode = Database.find_entry("groups", job.context)
    if job.interval == 0:
        for message in GlobalVariables.messages:
            message.delete()
        if len(GlobalVariables.gamers) >= 3:
            bot.send_message(chat_id=job.context, text="Game is starting...")
            GlobalVariables.message_del()
            GlobalVariables.game_status(True)
            game(bot, job)
            job.schedule_removal()
        else:
            bot.send_message(chat_id=job.context, text="Game has been aborted, not enough players")
            GlobalVariables.message_del()
            GlobalVariables.gamers_del()
            job.schedule_removal()
    else:
        job.interval -= 10
        message = bot.send_message(chat_id=job.context, text="Only {} seconds left to join the game...".
                                   format(job.interval), reply_markup=Buttons.join_button(langcode))
        GlobalVariables.message_add(message)


def game(bot, job):
    GlobalVariables.choose_chameleon(random.choice(GlobalVariables.gamers))
    bot.send_message(job.context, "The game has been started! These are the players:\n{}".format(
        "\n".join(GlobalVariables.gamer_list())), parse_mode=ParseMode.HTML)
    bot.send_message(job.context, theSource.word_list, reply_markup=Buttons.secret_button)
    temp = GlobalVariables.gamers
    random.shuffle(temp)
    GlobalVariables.shuffle_save(temp)
    bot.send_message(job.context, "{}, you are the first one to give me a word. Please do this".format(
        create_mention([GlobalVariables.shuffle[0].id, GlobalVariables.shuffle[0].name])), parse_mode=ParseMode.HTML,
                     reply_markup=ForceReply(selective=True))


def words(bot, update):
    if GlobalVariables.game_running:
        if update.message.reply_to_message.from_user.id == 586029498:
            # This try cause it currently registers every answer. May need to add a vote status and check for this.
            try:
                if update.effective_user.id == GlobalVariables.shuffle[len(GlobalVariables.words)].id:
                    GlobalVariables.words_add(
                        [GlobalVariables.shuffle[len(GlobalVariables.words)].name, update.message.text])
                    temp = len(GlobalVariables.words)
                    templist = []
                    for things in GlobalVariables.words:
                        templist.append("{}: {}".format(things[0], things[1]))
                    try:
                        bot.send_message(update.effective_chat.id,
                                         "Thanks. Now, its your turn, {}.\n\nCurrent Wordlist:\n{}".format(
                                             create_mention(
                                                 [GlobalVariables.shuffle[temp].id,
                                                  GlobalVariables.shuffle[temp].name]),
                                             "\n".join(
                                                 templist)),
                                         parse_mode=ParseMode.HTML, reply_markup=ForceReply(selective=True))
                    except IndexError:
                        bot.send_message(update.effective_chat.id,
                                         "Final list, we have to go to vote then:\n{} ".format("\n".join(templist)),
                                         parse_mode=ParseMode.HTML)
                        vote(bot, update)
            except IndexError:
                pass
            else:
                bot.send_message(update.effective_chat.id, "DENIED")


def vote(bot, update):
    votelist = GlobalVariables.votelist_create()
    bot.send_message(update.effective_chat.id,
                     "Votelist:\n\n{}".format("\n".join("{}: 0".format(voters) for voters in votelist)),
                     reply_markup=Buttons.vote(), parse_mode=ParseMode.HTML)


def join(bot, update):
    langcode = Database.find_entry("groups", update.effective_chat.id)
    if GlobalVariables.game_running:
        # May also need more game states so we can make this better
        message = bot.send_message("Please use the start button beneath this message to join the game :)",
                                   reply_markup=Buttons.join_button(langcode))
        GlobalVariables.message_add(message)
    else:
        bot.send_message(update.message.chat_id, "You need to start a game first, please use /start for that.")


def joining(bot, update):
    langcode = Database.find_entry("groups", update.effective_chat.id)
    query = update.callback_query
    skip = False
    for gamers in GlobalVariables.gamers:
        if gamers.id == query.from_user.id:
            query.answer(text="You joined already...", show_alert=True)
            skip = True
    if not skip:
        query.answer(text="You joined the game!")
        bot.send_message(chat_id=query.message.chat_id, text="{} joined the game.".format(
            create_mention([query.from_user.id, query.from_user.first_name])), parse_mode=ParseMode.HTML)
        gamer = Gamers(query.from_user.id, query.from_user.first_name)
        GlobalVariables.gamers_add(gamer)
        temp = GlobalVariables.gamer_list()
        GlobalVariables.messages[0].edit_text(
            text="Chameleon has been started! Please join the game.\nPlayers:\n{}".format(
                "\n".join(temp)), parse_mode=ParseMode.HTML, reply_markup=Buttons.join_button(langcode))


def leaving(bot, update):
    langcode = Database.find_entry("groups", update.effective_chat.id)
    query = update.callback_query
    skip = False
    for gamers in GlobalVariables.gamers:
        if gamers.id == query.from_user.id:
            query.answer(text="You left the game!")
            bot.send_message(chat_id=query.message.chat_id, text="{} left the game.".format(
                create_mention([query.from_user.id, query.from_user.first_name])), parse_mode=ParseMode.HTML)
            GlobalVariables.gamers_rem(gamers)
            GlobalVariables.messages[0].edit_text(
                parse_mode=ParseMode.HTML,
                reply_markup=Buttons.join_button(langcode))
            skip = True
    if not skip:
        query.answer(text="You need to join first...", show_alert=True)


def secreting(bot, update):
    query = update.callback_query
    if GlobalVariables.chameleon.id == query.from_user.id:
        bot.answerCallbackQuery(callback_query_id=query.id, text="You are the CHAMELEON",
                                show_alert=True)
    else:
        bot.answerCallbackQuery(callback_query_id=query.id, text=theSource.secret_word,
                                show_alert=True)


def voting(bot, update):
    query = update.callback_query
    voteid = update.callback_query.data[4:len(update.callback_query.data)]
    skip = False
    for voted in GlobalVariables.gamers:
        if voted.id == query.from_user.id:
            if voted.vote:
                query.answer(text="No voting twice ;P", show_alert=True)
                skip = True
    if not skip:
        print("Grr")
        for gamer in GlobalVariables.gamers:
            if int(voteid) == gamer.id:
                bot.send_message(chat_id=query.message.chat_id, text="{} voted for {}.".format(
                    create_mention([query.from_user.id, query.from_user.first_name]),
                    create_mention([gamer.id, gamer.name])), parse_mode=ParseMode.HTML)
                votelist = GlobalVariables.votelist_update(gamer.name)
                query.edit_message_text(
                    "Votelist:\n\n{}".format("\n".join("{}: {}".format(voter[0], voter[1]) for voter in votelist)),
                    reply_markup=Buttons.vote(), parse_mode=ParseMode.HTML)
                for gamers in GlobalVariables.gamers:
                    if query.from_user.id == gamers.id:
                        gamers.vote = True
                if all(gamer.vote is True for gamer in GlobalVariables.gamers):
                    bot.send_message(chat_id=query.message.chat_id, text="Voting stopped y'all")
                query.answer(text="You voted for {}".format(gamer.name))


def config_group(bot, update):
    langcode = Database.find_entry("users", update.effective_user.id, username=update.effective_user.first_name)
    found = False
    admins = bot.getChatAdministrators(update.message.chat_id)
    for ids in admins:
        if ids['user']["id"] == update.effective_user.id:
            found = True
            try:
                bot.send_message(update.effective_user.id,
                                 lang["change_settings_of_group"][langcode].format(update.effective_chat.title),
                                 reply_markup=Buttons.config(update.effective_chat.id))
            except Unauthorized:
                update.message.reply_text(text=lang["need_to_start_first"][langcode],
                                          reply_markup=Buttons.start(update.effective_user.id,
                                                                     update.effective_chat.id))
    if not found:
        update.message.reply_text(lang["need_to_be_admin"][langcode])


def startconfig(bot, update, args):
    langcode = Database.find_entry("users", update.effective_user.id)
    if not args:
        update.message.reply_text(text=lang["start_private"][langcode])
    else:
        payload = re.search(r"(\d+)\|(.+)", args)
        if payload:
            if update.effective_user.id == payload.group(1):
                bot.send_message(update.effective_user.id,
                                 lang["change_settings_of_group"][langcode]
                                 .format(bot.get_chat(payload.group(2)).title),
                                 reply_markup=Buttons.config(payload.group(2)))
            else:
                update.message.reply_text(text=lang["start_private"][langcode])


def config_private(bot, update):
    bot.send_message(update.effective_user.id, "You want to change your settings? Well, here you go then",
                     reply_markup=Buttons.config(update.effective_user.id))


def configing(_, update):
    query = update.callback_query
    todo = query.data[6:8]
    payload = re.search(r"\|(.+)", query.data)
    if todo == "lg":
        query.edit_message_text("So language it is. Please choose one from the list below",
                                reply_markup=Buttons.language(payload.group(1)))


def languaging(_, update):
    query = update.callback_query
    todo = query.data[10:12]
    payload = re.search(r"\|(.+)", query.data)
    if payload.group(1).startswith("-"):
        Database.update_entry_language("groups", payload.group(1), todo)
        query.edit_message_text("Successfully set the language to {}".format(todo))
    else:
        Database.update_entry_language("users", payload.group(1), todo)
        query.edit_message_text("Successfully set the language to {}".format(todo))


def translate(bot, update):
    bot.send_message(update.message.chat_id,
                     "You want to add/update a language? Great. Please choose one from the list."
                     "Use /cancel to cancel whatever you currently do.",
                     reply_markup=Buttons.languages())
    return LANGUAGE


def language(_, update):
    query = update.callback_query
    langcode = query.data[4:6]
    if langcode == "add":
        query.edit_message_text("Please join our translation group so we can walk you through the steps :)")
    else:
        query.edit_message_text("Great. Now, choose the string you want to update",
                                reply_markup=Buttons.updatelang(langcode))
    return STRING


def string(_, update):
    query = update.callback_query
    langcode = query.data[6:8]
    strings = query.data[8:len(query.data)]
    GlobalVariables.stringcode_save(langcode + strings)
    query.edit_message_text(
        "The current string is:\n\n<i>{}</i>\n\nPlease send me your improvement.".format(lang[strings][langcode]),
        parse_mode=ParseMode.HTML)
    return UPDATE


def new_string(bot, update):
    bot.send_message(chat_id=update.effective_chat.id,
                     text="Great. Your improvement is\n\n<i>{}</i>\n\nI will inform you if the devs added it to the "
                          "game. If you decide to abuse this feature to send random strings to us, we will ban you "
                          "from using it :)".format(update.message.text), parse_mode=ParseMode.HTML)
    bot.send_message(chat_id="@TheChameleon",
                     text="Hello there. User {} wants to improve string <b>{}</b> from language <b>{}</b>. Current "
                          "string:\n\n<i>{}</i>\n\nNew string\n\n<i>{}</i>".format(
                            create_mention([update.effective_user.id, update.effective_user.name]),
                            GlobalVariables.stringcode[2:len(GlobalVariables.stringcode)],
                            GlobalVariables.stringcode[0:2],
                            lang[GlobalVariables.stringcode[2:len(GlobalVariables.stringcode)]]
                            [GlobalVariables.stringcode[0:2]], update.message.text),
                     reply_markup=Buttons.string_buttons, parse_mode=ParseMode.HTML)
    GlobalVariables.string_save([update.message.text, update.effective_user.id])
    return ConversationHandler.END


def update_string(bot, update):
    query = update.callback_query
    if query.data[6:10] == "yes":
        lang[GlobalVariables.stringcode[2:len(GlobalVariables.stringcode)]][GlobalVariables.stringcode[0:2]] = \
            GlobalVariables.string[0]
        with open('./language.json', 'w') as outfile:
            json.dump(lang, outfile, indent=4, sort_keys=True)
        bot.send_message(chat_id=GlobalVariables.string[1],
                         text="Thanks so much for you submission, it made it to the game :)")
        Database.update_entry_translator(GlobalVariables.string[1], GlobalVariables.stringcode[0:2])
        query.edit_message_text("Added")
    else:
        bot.send_message(chat_id=GlobalVariables.string[1],
                         text="Sorry to inform you, we won't add your update :( Please join our translation group if "
                              "you want more informations why.")
        query.edit_message_text("DENIED")


def cancel(_, update):
    update.message.reply_text('Bye! I hope we can talk again some day.')
    return ConversationHandler.END


def main():
    tokencode = 'TOKEN'
    update = Updater(token=tokencode)
    dispatcher = update.dispatcher
    dispatcher.add_handler(CommandHandler('start', start, pass_job_queue=True, filters=Filters.group))
    dispatcher.add_handler(CommandHandler('join', join, filters=Filters.group))
    dispatcher.add_handler(MessageHandler(Filters.reply, words))
    dispatcher.add_handler(CallbackQueryHandler(joining, pattern="joining"))
    dispatcher.add_handler(CallbackQueryHandler(leaving, pattern="leaving"))
    dispatcher.add_handler(CallbackQueryHandler(secreting, pattern="secret word"))
    dispatcher.add_handler(CallbackQueryHandler(voting, pattern="vote"))
    dispatcher.add_handler(CommandHandler('config', config_group, filters=Filters.group))
    dispatcher.add_handler(CommandHandler('config', config_private, filters=Filters.private))
    dispatcher.add_handler(CallbackQueryHandler(configing, pattern="change"))
    dispatcher.add_handler(CallbackQueryHandler(languaging, pattern="updatelang"))
    dispatcher.add_handler(CommandHandler('start', startconfig, pass_args=True, filters=Filters.private))
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('translate', translate, filters=Filters.private)],

        states={
            LANGUAGE: [CallbackQueryHandler(language, pattern="lang")],

            STRING: [CallbackQueryHandler(string, pattern="string")],

            UPDATE: [MessageHandler(Filters.text, new_string)]
        },

        fallbacks=[CommandHandler('cancel', cancel)],
    )

    dispatcher.add_handler(conv_handler)
    update.start_polling()


if __name__ == '__main__':
    main()
