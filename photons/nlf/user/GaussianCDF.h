// GaussianCDF.h
#define EXPORT __declspec(dllexport)

extern "C" {
    EXPORT void GetFunctionName(char* name);
    EXPORT void GetFunctionValue(double* x, double* a, double* y);
    EXPORT void GetNumParameters(int* n);
    EXPORT void GetNumVariables(int* n);
}