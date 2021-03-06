/* Dumb Python C extension wrapper around wgrib */
#include <stdlib.h>
#include <Python.h>

// forward declare wgrib entry point
int wgrib(int argc, char **argv);


static const char *convertToCharArray(PyObject *py_val) {
    /* Performs naive conversion of python utf8/byte string to char array
    Returns pointer to 
    */
    PyObject *s = NULL;
    const char *converted_string = NULL;

    if( PyUnicode_Check(py_val) ) {  // python3 has unicode, but we convert to bytes
        s = PyUnicode_AsUTF8String(py_val);
    } else if( PyBytes_Check(py_val) ) {  // python2 has bytes already
        s = PyObject_Bytes(py_val);
    } else {
        // Not a string => Error, warning ...
        PyErr_SetString(PyExc_TypeError, "Not a string");
    }

    // If succesfully converted to bytes, then convert to C string
    if (s) {
        converted_string = PyBytes_AsString(s);
    }
    return converted_string;
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
    Py_ssize_t argc =  PyTuple_Size(args);
    Py_ssize_t retval;

    char **argv = (char **)calloc(sizeof(char*), (unsigned long)argc+1);
    const char **argv_const = (const char**) argv;

    if (argv == NULL) {
        if(!PyErr_Occurred()) 
            PyErr_SetString(PyExc_MemoryError, "Unable to allocate memory");
        return NULL;
    }

    for (unsigned int i=0; i < argc; i++) {
        //char *arg = NULL;
        PyObject *item = PyTuple_GetItem(args, i);
        if (!item) {
            return NULL;
        }
        argv[i] = (char *)convertToCharArray(item);
    }

    /* assign and parse string representing commands */

    retval = wgrib(argc, argv_const);

    /* clean up */
    free(argv);

    return PyLong_FromSsize_t(retval);
    Py_RETURN_NONE;
}

static PyMethodDef Methods[] = {
    {"main", py_main, METH_VARARGS, "wgrib main() python wrapper"},
    {"system_call", system_call, METH_VARARGS, "system() wrapper"},
    {NULL, NULL, 0, NULL}
};

/*
PyMODINIT_FUNC initwgrib(void) {
    (void) Py_InitModule("wgrib", Methods);
}
*/

struct module_state {
    PyObject *error;
};

#if PY_MAJOR_VERSION >= 3
#define GETSTATE(m) ((struct module_state*)PyModule_GetState(m))
#else
#define GETSTATE(m) (&_state)
static struct module_state _state;
#endif


#if PY_MAJOR_VERSION >= 3


static struct PyModuleDef moduledef = {
        PyModuleDef_HEAD_INIT,
        "wgrib",
        NULL,
        sizeof(struct module_state),
        Methods,
        NULL,
        NULL,
        NULL,
        NULL
};

#define INITERROR return NULL

PyMODINIT_FUNC
PyInit_wgrib(void)

#else
#define INITERROR return

void
initwgrib(void)
#endif
{
#if PY_MAJOR_VERSION >= 3
    PyObject *module = PyModule_Create(&moduledef);
#else
    PyObject *module = Py_InitModule("wgrib", Methods);
#endif

    if (module == NULL)
        INITERROR;
    struct module_state *st = GETSTATE(module);

    st->error = PyErr_NewException("wgrib.RuntimeError", NULL, NULL);
    if (st->error == NULL) {
        Py_DECREF(module);
        INITERROR;
    }

#if PY_MAJOR_VERSION >= 3
    return module;
#endif
}