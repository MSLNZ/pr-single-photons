// Gaussian Cumulative Distribution Function.
#include <math.h>  // erf, sqrt
#include <string.h>  // strcpy_s
#include "GaussianCDF.h"

void GetFunctionName(char* name) {
    // The name must begin with f followed by a positive integer followed by a colon.
    // The remainder of the string is for information for the user.
    strcpy_s(name, 255, "f1: GaussianCDF f1=amplitude/2*(1+erf((x-mu)/(sigma*sqrt(2))))+offset");
}

void GetFunctionValue(double* x, double* a, double* y) {
    // a[0]=amplitude, a[1]=mu, a[2]=sigma, a[3]=offset
    *y = 0.5 * a[0] * (1.0 + erf((x[0] - a[1]) / (a[2] * sqrt(2.0)))) + a[3];
}

void GetNumParameters(int* n) {
    // There are 4 parameters: amplitude, mu, sigma, offset
    *n = 4;
}

void GetNumVariables(int* n) {
    // There is only 1 independent variable: x
    *n = 1;
}