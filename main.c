#include <unistd.h>
#include <string.h>
#include <stdlib.h>

int main(int argc, const char **argv) {
  int n_threads = atoi(argv[1]);
  int sleep_time;
  if(strcmp(argv[2],"data1") == 0) {
    sleep_time = 1000000;
  } else if(strcmp(argv[2],"data2") == 0) { 
    sleep_time = 500000;
  } else if(strcmp(argv[2],"data3") == 0) { 
    sleep_time = 1400000;
  }
  usleep(sleep_time/n_threads);
  return 0;
}

