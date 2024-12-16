#include <unistd.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

int main(int argc, const char **argv) {
  int n_threads = atoi(argv[1]);
  int sleep_time;
  if(strcmp(argv[2],"data1") == 0) {
    sleep_time = 1000000;
  } else if(strcmp(argv[2],"data2") == 0) { 
    sleep_time = 500000;
  } else if(strcmp(argv[2],"data3") == 0) { 
    sleep_time = 1000000;
  }
  usleep(sleep_time/n_threads);
  printf("%f", ((float)sleep_time/n_threads)/1e6);
  fprintf(stderr, "%f", (float)sleep_time/1e6);
  return 0;
}

