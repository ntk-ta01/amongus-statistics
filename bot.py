import discord
from discord.ext import commands
import requests
import os
from PIL import Image, ImageOps
import pyocr
import pyocr.builders
from sys import stderr
# import matplotlib.pyplot as plt

token = os.environ['DISCORD_BOT_TOKEN']

DATA_KEY = ['Bodies Reported', 'Emergencies Called', 'Tasks Completed',
            'All Tasks Completed', 'Sabotages Fixed', 'Impostor Kills',
            'Times Murdered', 'Times Ejected', 'Crewmate Streak',
            'Times Impostor', 'Times Crewmate', 'Games Started',
            'Games Finished', 'Impostor Vote Wins', 'Impostor Kill Wins',
            'Impostor Sabotage Wins', 'Crewmate Vote Wins',
            'Crewmate Task Wins']


def read_image(filename) -> str:
    tools = pyocr.get_available_tools()
    # The tools are returned in the recommended order of usage
    tool = tools[0]

    im = Image.open(filename).convert('L')
    im.point(lambda x: 0 if x < 230 else x)  # Binarization
    im_invert = ImageOps.invert(im)  # Negative / positive reversal
    # im_invert.save('invert.png')

    txt = tool.image_to_string(
        im_invert,
        lang="eng",
        builder=pyocr.builders.TextBuilder(tesseract_layout=6)
    )

    # print(txt)
    return txt


def is_num(s):
    try:
        int(s)
    except ValueError:
        return False
    else:
        return True


class User:
    def __init__(self, name: str, txt: str):
        self.name = name
        self.data = {key: -100_000_000 for key in DATA_KEY}
        idx = 0
        for line in txt.split('\n'):
            KEY = DATA_KEY[idx]
            key_idx = line.find(KEY)
            if key_idx == -1:
                continue
            words = [word.strip() for word in line[key_idx:].split(':')]
            words[1] = words[1].split()[0]
            words = words[:2]
            if len(words) < 2:
                msg = "error: The specified number of " + \
                    "characters could not be read (in", KEY + ")."
                print(msg, file=stderr)
            else:
                try:
                    self.data[KEY] = int(words[1])
                except ValueError:
                    print("error: String that cannot be converted to numbers were\
 included (in", KEY + ").", file=stderr)
            idx += 1
            if idx == len(DATA_KEY):
                break
        self.win_num = 0
        self.impostor_win_num = 0
        self.crewmate_win_num = 0
        for k, v in self.data.items():
            if "Win" in k:
                self.win_num += v
                if "Impostor" in k:
                    self.impostor_win_num += v
                else:
                    self.crewmate_win_num += v

        """ create a pie chart
            but the pie chart is lame…
            win_rate = float("{:.2%}".format(
                self.win_num / self.data['Games Finished']).strip("%"))
            win_lose = [win_rate, 100 - win_rate]
            plt.pie(win_lose,
                    colors=("#628FDB", "#2B3752"),
                    wedgeprops={'linewidth': 2, 'edgecolor': '#1A1B27'},
                    startangle=90,
                    counterclock=False
                    )
            plt.axis('equal')
            center_circle = plt.Circle((0, 0), 0.7,
                                       color='#1A1B27', fc='#1A1B27')
            fig = plt.gcf()
            fig.gca().add_artist(center_circle)
            fig.gca().annotate("WIN RATE\n{:.1%}".format(
                self.win_num / self.data['Games Finished']),
                xy=(0, 0), fontsize=30, fontfamily='sans-serif',
                fontweight='bold', color="#38BDAE", va="center", ha="center")
            fig.patch.set_alpha(0)
            plt.savefig('pie_chart')
        """


class Server:
    def __init__(self) -> None:
        self.user_list = {}

    def add(self, user: User):
        self.user_list[user.name] = user

    def get(self, user_name: str) -> User:
        return self.user_list[user_name]

    def rank_win_rate(self) -> list:
        values = []
        for user in self.user_list.values():
            values.append((user.win_num / user.data['Games Finished'],
                           user.name))
        values.sort(reverse=True)
        return values

    def rank_win_rate_when_impostor(self) -> list:
        values = []
        for user in self.user_list.values():
            values.append((user.impostor_win_num / user.data['Times Impostor'],
                           user.name))
        values.sort(reverse=True)
        return values

    def rank_win_rate_when_crewmate(self) -> list:
        values = []
        for user in self.user_list.values():
            values.append((user.crewmate_win_num / user.data['Times Crewmate'],
                           user.name))
        values.sort(reverse=True)
        return values

    def rank_kill(self) -> list:
        values = []
        for user in self.user_list.values():
            values.append((
                user.data['Impostor Kills'] / user.data['Times Impostor'],
                user.name))
        values.sort(reverse=True)
        return values

    def rank_alltask(self) -> list:
        values = []
        for user in self.user_list.values():
            values.append((
                user.data['All Tasks Completed'] / user.data['Times Crewmate'],
                user.name))
        values.sort(reverse=True)
        return values

    def rank_sabotagefix(self) -> list:
        values = []
        for user in self.user_list.values():
            values.append((
                user.data['Sabotages Fixed'] / user.data['Games Finished'],
                user.name))
        values.sort(reverse=True)
        return values


intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix='>', intents=intents)
server = Server()


@bot.command()
async def add(ctx, *args):
    """
    Add user data with your statistics image file. You can use --name args.
    """
    if len(ctx.message.attachments) < 1:
        await ctx.send("One image file is required")
        return
    filename = ctx.message.attachments[0].filename
    url = ctx.message.attachments[0].url
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        with open(filename, 'wb') as f:
            f.write(r.content)
    else:
        await ctx.send("Failed to get the image file")
        return
    txt = read_image(filename)
    os.remove(filename)
    name = ctx.author.name
    if len(args) > 0:
        if "--name" != args[0]:
            await ctx.send("Invalid args")
            return
        if len(args) == 1:
            await ctx.send("Specify the name of the user you want to add")
            return
        for m in ctx.guild.members:
            if m.name == args[1] or m.nick == args[1]:
                name = args[1]
                break
        else:
            await ctx.send("Invalid user name")
            return
    user = User(name, txt)
    server.add(user)
    ret = "add " + name + "!"
    await ctx.send(ret)


@bot.command()
async def show(ctx, *args):
    """
    Show user's data. You can user --name, --rank, and --userlist args.
    """
    if len(server.user_list) < 1:
        await ctx.send("The server dosen't have any data….")
    elif (len(args) < 1 or args[0] == "--name"):
        user_name = ctx.author.name
        if len(args) > 1 and "--name" == args[0]:
            for m in ctx.guild.members:
                if m.name == args[1] or m.nick == args[1]:
                    user_name = args[1]
                    break
            else:
                await ctx.send("Invalid user name")
                return
        user = server.get(user_name)
        ret = "Win rate(when Impostor or Crewmate): {:.2%}\n".format(
            user.win_num / user.data['Games Finished'])
        ret += "Win rate(when Impostor): {:.2%}\n".format(
            user.impostor_win_num / user.data['Times Impostor'])
        ret += "Win rate(when Crewmate): {:.2%}\n".format(
            user.crewmate_win_num / user.data['Times Crewmate'])
        ret += "Kills per Impostor: {:.2f}\n".format(
            user.data['Impostor Kills'] / user.data['Times Impostor'])
        ret += "Tasks Completed rate: {:.2%}\n".format(
            user.data['All Tasks Completed'] / user.data['Times Crewmate'])
        ret += "Sabotages Fixed / Games: {:.2f}".format(
            user.data['Sabotages Fixed'] / user.data['Games Finished'])
        await ctx.send(ret)
    elif args[0] == "--rank":
        show_num = 3
        if len(args) > 1 and is_num(args[1]):
            show_num = int(args[1])
        ret = "leaderboard! (Win Rate) \n"
        ret += "\n".join("rank {2} {1} : {0:.2%} win".format(tup[0], tup[1],
                                                             rank)
                         for rank, tup in enumerate(
                             server.rank_win_rate()[:show_num], start=1))
        ret += "\n\nleaderboard! (Impostor Win Rate) \n"
        ret += "\n".join("rank {2} {1} : {0:.2%} win".format(tup[0], tup[1],
                                                             rank)
                         for rank, tup in enumerate(
                             server.rank_win_rate_when_impostor()[:show_num],
            start=1))
        ret += "\n\nleaderboard! (Crewmate Win Rate) \n"
        ret += "\n".join("rank {2} {1} : {0:.2%} win".format(tup[0], tup[1],
                                                             rank)
                         for rank, tup in enumerate(
                             server.rank_win_rate_when_crewmate()[:show_num],
            start=1))
        ret += "\n\nleaderboard! (Kill / Times Impostor) \n"
        ret += "\n".join("rank {2} {1} : {0:.2f} killed".format(tup[0], tup[1],
                                                                rank)
                         for rank, tup in enumerate(
                             server.rank_kill()[:show_num], start=1))
        ret += "\n\nleaderboard! (All Tasks Completed / Times Crewmate) \n"
        ret += "\n".join("rank {2} {1} : {0:.2%} completed".format(
            tup[0], tup[1],
            rank)
            for rank, tup in enumerate(
            server.rank_alltask()[:show_num], start=1))
        ret += "\n\nleaderboard! (Sabotages Fixed / Number of Games) \n"
        ret += "\n".join("rank {2} {1} : {0:.2f} fixed".format(tup[0], tup[1],
                                                               rank)
                         for rank, tup in enumerate(
                             server.rank_sabotagefix()[:show_num], start=1))
        await ctx.send(ret)
    elif args[0] == "--diff":
        await ctx.send("I'll implement it one day!")
    elif args[0] == "--userlist":
        await ctx.send(", ".join([k for k in server.user_list.keys()]))
    else:
        await ctx.send("invalid command ><")


bot.run(token)
