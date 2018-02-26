/* Dumb Python C extension wrapper around wgrib */

#ifdef _WIN32
#include<Python.h>
#else
#include<Python/Python.h>
#endif

#include<stdlib.h>
#include<string.h>

#ifndef C_MAXARGS
#define C_MAXARGS 1000 /* large but not infinite... */
#endif

//Forward declare wgrib_main
int GRIB_MAIN(int argc, char **argv);

/**
 * Split a line into separate words.
 * 
 * Note: Taken from: https://stackoverflow.com/questions/5534620/mimicking-the-shell-argument-parser-in-c
 */
static void splitLine(char *pLine, char **pArgs) {
    char *pTmp = strchr(pLine, ' ');

    if (pTmp) {
        *pTmp = '\0';
        pTmp++;
        while ((*pTmp) && (*pTmp == ' ')) {
            pTmp++;
        }
        if (*pTmp == '\0') {
            pTmp = NULL;
        }
    }
    *pArgs = pTmp;
}

/**
 * Breaks up a line into multiple arguments.
 *
 * @param io_pLine Line to be broken up.
 * @param o_pArgc Number of components found.
 * @param io_pargc Array of individual components
 * 
 * Note: Taken from: https://stackoverflow.com/questions/5534620/mimicking-the-shell-argument-parser-in-c
 */
static void parseArguments(char *io_pLine, int *o_pArgc, char **o_pArgv) {
    char *pNext = io_pLine;
    size_t i;
    int j;
    int quoted = 0;
    size_t len = strlen(io_pLine);

    // Protect spaces inside quotes, but lose the quotes
    for(i = 0; i < len; i++) {
        if ((!quoted) && ('"' == io_pLine[i])) {
            quoted = 1;
            io_pLine[i] = ' ';
        } else if ((quoted) && ('"' == io_pLine[i])) {
            quoted = 0;
            io_pLine[i] = ' ';
        } else if ((quoted) && (' ' == io_pLine[i])) {
            io_pLine[i] = '\1';
        }
    }

    // init
    memset(o_pArgv, 0x00, sizeof(char*) * C_MAXARGS);
    *o_pArgc = 1;
    o_pArgv[0] = io_pLine;

    while ((NULL != pNext) && (*o_pArgc < C_MAXARGS)) {
        splitLine(pNext, &(o_pArgv[*o_pArgc]));
        pNext = o_pArgv[*o_pArgc];

        if (NULL != o_pArgv[*o_pArgc]) {
            *o_pArgc += 1;
        }
    }

    for(j = 0; j < *o_pArgc; j++) {
        len = strlen(o_pArgv[j]);
        for(i = 0; i < len; i++) {
            if('\1' == o_pArgv[j][i]) {
                o_pArgv[j][i] = ' ';
            }
        }
    }
}

static PyObject *
system_call(PyObject *self, PyObject *args)
{
    const char *command;
    int sts;

    if (!PyArg_ParseTuple(args, "s", &command))
        return NULL;
    sts = system(command);
    return PyLong_FromLong(sts);
}

static PyObject *
py_main(PyObject *self, PyObject *args)
{
    int argc = 0;
    char **argv = NULL;
    const char *command;
    char *cmd;

    if (!PyArg_ParseTuple(args, "s", &command))
    {
        return NULL;
    }

    /* assign and parse string representing commands */
    cmd = (char *)calloc(strlen(command)+1, sizeof(char));
    strcpy(cmd, command);
    parseArguments(cmd, &argc, argv);

    /* clean up */
    free(cmd);
    for (int i=0; i < argc; i++) {
        free(argv[i]);
    }
    free(argv);

    Py_RETURN_NONE;
}

static PyMethodDef Methods[] = {
    {"main", py_main, METH_VARARGS, "wgrib main() python wrapper"},
    {"system_call", system_call, METH_VARARGS, "system() wrapper"},
    {NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC initwgrib(void) {
    (void) Py_InitModule("wgrib", Methods);
}
