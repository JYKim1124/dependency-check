// matmul.c
#include <stdio.h>
// matmul.c
int A[100][100];
int B[100][100];
int C[100][100];

int main() {
  int i, j, k;
  #pragma scop
  for (i = 0; i < 1024; i++) {
      for (j = 0; j < 1024; j++) {
          C[i][j] = 0;
          for (k = 0; k < 1024; k++)
              C[i][j] = C[i][j] + A[i][k] * B[k][j];
      }
  }

  #pragma endscop

  return 0;
}


