# Constants to centralize configurable names/messages
HELP_CHANNEL_NAME = "help-queue-chat"
ONLINE_TAS_VC_NAME = "Online TAs"
IN_PERSON_CHANNEL_NAME = "In Person with Student"
WAITING_ROOM_NAME = "Waiting Room"
BREAKOUT_NAMES = ("Breakout Room A", "Breakout Room B", "Breakout Room C")
STUDENT_INFO_WIDTH = 25
NEXT_IN_LINE_MSG = "You are next in line! A TA will be with you shortly."

# message timeouts
SHORT_TIMEOUT = 10
DEFAULT_TIMEOUT = 20
LONG_TIMEOUT = 60 * 5
OPEN_TTL = 60 * 60 * 4
CLOSE_TTL = 60 * 60 * 13

# Common response templates
NOW_HELPING_TEMPLATE = "{ta} is now helping {student}"
QUEUE_OPENED = "Queue opened."
QUEUE_CLOSED = "Queue closed."
QUEUE_ALREADY_OPEN = "Queue is already open!"
QUEUE_ALREADY_CLOSED = "Queue is already closed!"