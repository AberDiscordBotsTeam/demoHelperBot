import asyncio

import discord
from discord import Member, VoiceChannel, Guild, ChannelType
from discord import Permissions
from discord.ext import commands
from discord.ext.commands import Context

import logging
import shelve

from cogs import adminRoles, addMessageFile
from helpers import listPrint

queues = {'dummy': []}


# somewhere to store the last message sent per guild per channel.
# key used is the guild name + the channel name.
# using ctx.message.delete() to the message that called a particular command.
# any messages sent that you want cleared next time bot is used
# save into prevMessages e.g prevMessages[k] = await ctx.send(...)
prevMessages = {'dummy': None}


async def rmPrevMessage(ctx: Context, k):
    """
    remove the message associated with the key (k) from the store and delete it if it still exists on the server.
    called on the commands you want to remove the previous message before putting in new one.
    """
    if k in prevMessages.keys():
        prevM = prevMessages[k]
        if prevM:
            botPerms: Permissions = ctx.channel.permissions_for(ctx.me)
            if botPerms.manage_messages:  # only do if bot has permission otherwise ignore
                try:
                    await prevM.delete()
                except:
                    pass  # ignore
            prevMessages[k] = None


async def rmCMDMessage(ctx: Context):
    """
    delete the command message for the context provided if bot has required perms.
    """
    botPerms: Permissions = ctx.channel.permissions_for(ctx.me)
    if botPerms.manage_messages:  # only do if bot has permission otherwise ignore
        await ctx.message.delete()


def setup(bot):
    """
    Setup the cogs in this extension
    """
    bot.add_cog(Students(bot))
    bot.add_cog(Demonstrators(bot))


def getQueue(serverName: str):
    """
    Get the relevant queue for the server
    :param serverName: the server you want the queue for
    :return: The queue for the server
    """
    if serverName in queues.keys():
        return queues.get(serverName)
    else:
        queues[serverName] = []
        return queues.get(serverName)


def getCustomAddMessage(serverName: str):
    """
    Gets the custom add message for the server
    :param serverName: the server you want the queue for
    :return: The add message for this server.
    """
    with shelve.open(addMessageFile) as db:
        if str(serverName) in db:
            return db.get(str(serverName))
        else:
            return 'Please join the `Wait for help` voice channel and wait to be moved to another voice channel'


class Demonstrators(commands.Cog):
    """
    Commands for demonstrators and Admins
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_any_role(*adminRoles)
    async def next(self, ctx: Context):
        """
        Get the next student in the queue
        """
        k = ctx.guild.name + ctx.channel.name
        await rmPrevMessage(ctx, k)
        queue = getQueue(ctx.guild)
        if len(queue) > 0:
            next = queue.pop(0)
            logging.info('{0} next {1}'.format(ctx.guild, next))
            if next is not None:
                prevMessages[k] = await ctx.send(
                    'The next student in the queue is {0}, {1} will be with you shortly to signoff or help you.'.format(
                        next.mention, ctx.message.author.mention))
        else:
            prevMessages[k] = await ctx.send('No more students in the queue.')
        await rmCMDMessage(ctx)

    @commands.command()
    @commands.has_any_role(*adminRoles)
    async def print(self, ctx: Context):
        """
        Print out the students in the queue
        """
        k = ctx.guild.name + ctx.channel.name
        await rmPrevMessage(ctx, k)

        logging.info('{0} queue {1}'.format(ctx.guild, getQueue(ctx.guild)))
        queue = getQueue(ctx.guild)
        temp = []
        for x in queue:
            temp.append(x.mention)
        queue = temp
        if queue is None or len(queue) == 0:
            prevMessages[k] = await ctx.send('No students in the Queue.')
        else:
            prevMessages[k] = await ctx.send('Remaining students in the queue are {0}'.format(listPrint(queue)))
        await rmCMDMessage(ctx)

    @commands.command()
    @commands.has_any_role(*adminRoles)
    async def nextV2(self, ctx:Context):
        """
        pull the student to a voice channel
        """
        k = ctx.guild.name + ctx.channel.name
        await rmPrevMessage(ctx, k)

        queue = getQueue(ctx.guild)

        if len(queue) > 0:
            nextStudent = queue.pop(0)
            logging.info('{0} next {1}'.format(ctx.guild, nextStudent))
            if nextStudent is not None:
                nextStudent = updateMember(ctx, nextStudent)
                message = 'The next student in the queue is {0}, '.format(
                            nextStudent.mention)
                if await pullToVoice(ctx, nextStudent):
                    message = message + 'They have been moved to your help voice channel. '
                if await assignRole(ctx, nextStudent):
                    message = message + 'They have been assigned the role to view this channel. '
                if message[-2:-1] == ',':
                    message = message + '{0} can now help you in {1}.'\
                        .format(ctx.message.author.mention, ctx.channel.mention)
                prevMessages[k] = await ctx.send(message)
        else:
            prevMessages[k] = await ctx.send('No more students in the queue.')
        await rmCMDMessage(ctx)


def updateMember(ctx:Context, m:Member):
    for m1 in ctx.guild.members:
        if m1.id == m.id:
            return m1
    return m


async def pullToVoice(ctx:Context, nextStudent: Member):
    if nextStudent.voice and nextStudent.voice.channel:
        voiceChannel = None
        for channel in ctx.guild.channels:
            if channel.name == ctx.channel.name and channel.type is ChannelType.voice:
                voiceChannel = channel
                break
        if voiceChannel:
            await nextStudent.move_to(voiceChannel)
        return True
    else:
        return False


async def assignRole(ctx:Context,member:Member):
    #todo implement
    pass


class Students(commands.Cog):
    """
    Commands for students
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def add(self, ctx: Context):
        """
        Adds the student to the help queue
        """
        k = ctx.guild.name + ctx.channel.name
        await rmPrevMessage(ctx, k)

        s = ctx.message.author
        q = getQueue(ctx.guild)
        if s not in q:
            q.append(s)
            logging.info('{0} add {1}'.format(ctx.guild, s))
            prevMessages[k] = await ctx.send(
                s.mention + ' has been added to the queue. ' + getCustomAddMessage(ctx.guild))
        else:
            prevMessages[k] = await ctx.send(s.mention + ' is already in the queue.')
        await rmCMDMessage(ctx)

    @commands.command()
    async def remove(self, ctx: Context):
        """
        Removes the student from the help queue
        """
        k = ctx.guild.name + ctx.channel.name
        await rmPrevMessage(ctx, k)

        s = ctx.message.author
        q = getQueue(ctx.guild)
        if s in q:
            q.remove(s)
            logging.info('{0} remove {1}'.format(ctx.guild, s))
            prevMessages[k] = await ctx.send(s.mention + ' has been removed from queue.')
        else:
            prevMessages[k] = await ctx.send(s.mention + ' is not in the queue.')
        await rmCMDMessage(ctx)



