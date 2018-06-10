"""Disk And Execution MONitor (Daemon)

Configurable daemon behaviors:

   1.) The current working directory set to the "/" directory.
   2.) The current file creation mode mask set to 0.
   3.) Close all open files (1024).
   4.) Redirect standard I/O streams to "/dev/null".

A failed call to fork() now raises an exception.

References:
   1) Advanced Programming in the Unix Environment: W. Richard Stevens
   2) Unix Programming Frequently Asked Questions:
         http://www.erlenstar.demon.co.uk/unix/faq_toc.html
"""

# Standard Python modules.
import os               # Miscellaneous OS interfaces.
import sys              # System-specific parameters and functions.

# Default daemon parameters.
# File mode creation mask of the daemon.
UMASK = 0

# Default working directory for the daemon.
#WORKDIR = "/"
WORKDIR = "./"

# Default maximum for the number of available file descriptors.
MAXFD = 1024

# The standard I/O file descriptors are redirected to /dev/null by default.
if (hasattr(os, "devnull")):
    REDIRECT_TO = os.devnull
else:
    REDIRECT_TO = "/dev/null"

def createDaemon():
    try:
        pid = os.fork()
    except OSError as e:
        #raise Exception, "%s [%d]" % (e.strerror, e.errno)
        raise e

    if (pid == 0):	# The first child.
        os.setsid()

        try:
            pid = os.fork()	# Fork a second child.
        except OSError as e:
            #raise Exception, "%s [%d]" % (e.strerror, e.errno)
            raise e

        if (pid == 0):	# The second child.
            os.chdir(WORKDIR)
            os.umask(UMASK)
        else:
            os._exit(0)	# Exit parent (the first child) of the second child.
    else:
      os._exit(0)	# Exit parent of the first child.

    import resource		# Resource usage information.
    maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
    if (maxfd == resource.RLIM_INFINITY):
        maxfd = MAXFD

    # Iterate through and close all file descriptors.
    for fd in range(0, maxfd):
        try:
            os.close(fd)
        except OSError:	# ERROR, fd wasn't open to begin with (ignored)
            pass

    os.open(REDIRECT_TO, os.O_RDWR)	# standard input (0)

    # Duplicate standard input to standard output and standard error.
    os.dup2(0, 1)			# standard output (1)
    os.dup2(0, 2)			# standard error (2)

    return(0)

if __name__ == "__main__":

    retCode = createDaemon()

    # The code, as is, will create a new file in the root directory, when
    # executed with superuser privileges.  The file will contain the following
    # daemon related process parameters: return code, process ID, parent
    # process group ID, session ID, user ID, effective user ID, real group ID,
    # and the effective group ID.  Notice the relationship between the daemon's
    # process ID, process group ID, and its parent's process ID.

    procParams = """
    return code = %s
    process ID = %s
    parent process ID = %s
    process group ID = %s
    session ID = %s
    user ID = %s
    effective user ID = %s
    real group ID = %s
    effective group ID = %s
    """ % (retCode, os.getpid(), os.getppid(), os.getpgrp(), os.getsid(0),
    os.getuid(), os.geteuid(), os.getgid(), os.getegid())

    open("createDaemon.log", "w").write(procParams + "\n")

    sys.exit(retCode)
