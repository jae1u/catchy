#include <stdio.h>
#include <string.h>

int main()
{
    setvbuf(stdin, 0, 2, 0);
    setvbuf(stdout, 0, 2, 0);
    setvbuf(stderr, 0, 2, 0);
    
    char secret[0x20] = "lol_lol_lol_lol";
    char what_is_your_name[0x20];

    printf("name: ");
    scanf("%s", what_is_your_name);

    if(!strcmp(secret, "give_me_some_flag"))
        system("cat flag");
    else if(!strcmp(secret, "lol_lol_lol_lol"))
        printf("nothing changed?\n");
    else
        printf("something changed!, %s\n", secret);
}