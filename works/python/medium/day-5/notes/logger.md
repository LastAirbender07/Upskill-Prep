doubts:

1. why level has backup of backup ?

```
    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
```

here "LOG_LEVEL" is initialized in env and if not its default value is "INFO"

but what is "LOG_LEVEL" is set as "TYSON" ??

level = getattr(logging, TYSON, logging.INFO)
This handles unknown values with a default value INFO

2. why do we need a handler ?
```
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
```

so aparently the handler "handles" the logs - it can either be printed in the terminal as stdout or written to a File or even sent as an email etc..

the level here - sets whats to be logged and handled.
Priority order:
- debug
- info
- warn
- error
- critical

3. where does formatter get the input attrs from ?
```
        formatter = ColoredFormatter(
            fmt="%(log_color)s[%(asctime)s] %(levelname)-8s %(name)s:%(reset)s %(message)s",
            datefmt="%H:%M:%S",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
        )
```

these actually come from the thing that was used for logging.
example logger.info("server started")
the logger module already has the level, time, logger component


4. whats this: logger.propagate = False

so aparently loggers can be initialized ib=n various modules - which means a child could also have a logger with its paraent. so without this the log will be logged both in child and parent
