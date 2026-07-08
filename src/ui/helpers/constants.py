
# Constants to centralize configurable names/messages

class Categories:
    HELP_QUEUE_CATEGORY = "Help Queue"

class Channels:
    HELP_CHANNEL_NAME = "help-queue-channel"
    TA_TEXT_CHANNEL_NAME = "ta-bot-channel"
    TA_VOICE_CHANNEL_NAME = "Online TAs"
    WAITING_ROOM_NAME = "Waiting Room"
    BREAKOUT_NAMES = ("Breakout Room A", "Breakout Room B", "Breakout Room C")
    IN_PERSON_CHANNEL_NAME = "In Person with Student"

class Messages:
    QUEUE_OPEN_MESSAGE = "The Help Queue is now open!"
    QUEUE_CLOSE_MESSAGE = "The Help Queue is now closed. If you are still on the queue, the TAs will help until their hours are over."
    STUDENT_INFO_WIDTH = 25
    NEXT_IN_LINE_MSG = "You are next in line! A TA will be with you shortly."
    # Common response templates
    NOW_HELPING_TEMPLATE = "{ta} is now helping {student}"
    QUEUE_OPENED = "Queue opened."
    QUEUE_CLOSED = "Queue closed."
    QUEUE_ALREADY_OPEN = "Queue is already open!"
    QUEUE_ALREADY_CLOSED = "Queue is already closed!"
    # message timeouts
    SHORT_TIMEOUT = 10
    DEFAULT_TIMEOUT = 20
    LONG_TIMEOUT = 60 * 5

class Roles:
    TA_ROLE = "TA"
    PROFESSOR_ROLE = "Professor"

class Config:
    QUEUE_SCHEDULE = "daily_queue_hours"
    