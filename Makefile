build: main.c
	gcc -o sleeper main.c
	date +%s
	>&2 echo 10
clean:
	rm sleeper
