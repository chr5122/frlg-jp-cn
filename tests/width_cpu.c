/* Project-owned synthetic CPU fixture; no game/native routine/font payload.
 * Stop BEFORE every native continuation, including LG's unsafe table target. */
#include <mgba/core/core.h>
#include <mgba/core/log.h>
#include <mgba-util/vfs.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define SIZE 0x1000000u
#define STACK 0x03007E00u
static unsigned cases=0;
static void quiet(struct mLogger *l,int c,enum mLogLevel v,const char *f,va_list a) {
    (void)l;(void)c;(void)v;(void)f;(void)a;
}
static void need(int ok,const char *message) {
    if (!ok) { fprintf(stderr,"FAIL case%u: %s\n",cases,message);exit(1); }
}
static void set(struct mCore *c,const char *name,uint32_t value) {
    need(c->writeRegister(c,name,&value),"write register");
}
static uint32_t get(struct mCore *c,unsigned n) {
    char name[8];uint32_t value=0;
    snprintf(name,sizeof(name),"r%u",n);
    need(c->readRegister(c,name,&value),"read register");return value;
}
static size_t load(const char *path,uint8_t *p,size_t limit) {
    FILE *f=fopen(path,"rb");need(f!=NULL,"open own code");
    size_t n=fread(p,1,limit,f);need(!ferror(f) && fgetc(f)==EOF,"code size/read");fclose(f);return n;
}
struct input { uint32_t address; unsigned owned; };
static void input_byte(struct mCore *c,uint32_t at,uint8_t value) {
    if(at>=0x08000000 && at<0x09000000)c->rawWrite8(c,at,-1,value);
    else c->busWrite8(c,at,value);
}
static const struct input fr_inputs[]={
    {0x086CFFFF,0},{0x086D0000,1},{0x0872FFFD,1},{0x08730000,0},
    {0x02021C00,1},{0x0203FFFD,1},{0x02040000,0},
    {0x03000000,1},{0x03007FFD,1},{0x03008000,0},{0x08B11000,0}};
static const struct input lg_inputs[]={
    {0x02021BFF,0},{0x02021C00,1},{0x02021DFD,1},{0x02021E00,0},
    {0x08B0FFFF,0},{0x08B10000,1},{0x08B2F62D,1},{0x08B2F630,0},
    {0x08BC0A3F,0},{0x08BC0A40,1},{0x08BFFFFD,1},{0x08C00000,0},
    {0x08DA1000,1},{0x08DA7FFD,1},{0x08DA8000,0},{0x08DA8FFF,0},
    {0x08DA9000,1},{0x08DB7FFD,1},{0x08DB8000,0},
    {0x02010000,1},{0x0201055D,1},{0x02010560,0},
    {0x020132B4,0},{0x02013301,0},{0x02013304,0},
    {0x0202B2B4,1},{0x0202B301,1},{0x0202B304,0}};

int main(int argc,char **argv) {
    need(argc==4,"usage: width_cpu fr|lg scanners.bin alias.bin-or-unused");
    int fr=strcmp(argv[1],"fr")==0;need(fr || strcmp(argv[1],"lg")==0,"game argument");
    uint8_t *rom=malloc(SIZE);need(rom!=NULL,"allocate synthetic memory");memset(rom,0xFF,SIZE);
    uint8_t raw[512];size_t n=load(argv[2],raw,sizeof(raw));
    need(n==(fr?144u:384u),"scanner size");memcpy(rom+(fr?0x7C0048:0xBC0000),raw,n);
    if(fr) {n=load(argv[3],raw,sizeof(raw));need(n==36,"alias size");memcpy(rom+0x7C065C,raw,n);}
    /* Generated F7+BE-u16 test streams. No real glyph or translated text. */
    const unsigned gids[]={0,0x100,0x92A,0x92E,0x92F,0xA00,0xAFF,0xB00,0xFFFF};
    const struct input *inputs=fr?fr_inputs:lg_inputs;
    unsigned count=fr?sizeof(fr_inputs)/sizeof(*inputs):sizeof(lg_inputs)/sizeof(*inputs);
    struct mLogger logger={.log=quiet};mLogSetDefaultLogger(&logger);
    struct mCore *c=mCoreCreate(mPLATFORM_GBA);need(c && c->init(c),"init mGBA");mCoreInitConfig(c,NULL);
    struct VFile *vf=VFileFromConstMemory(rom,SIZE);need(vf && c->loadROM(c,vf),"load synthetic memory");c->reset(c);
    c->busWrite32(c,0x0203AC94,0x02010000);c->busWrite32(c,0x0203B0B4,0x02028000);
    for(unsigned i=0;i<count;i++) for(unsigned j=0;j<sizeof(gids)/sizeof(*gids);j++)
    for(unsigned variable=0;variable<2;variable++) for(unsigned wrap=0;wrap<2;wrap++) {
        uint32_t at=inputs[i].address;unsigned gid=gids[j],owned=inputs[i].owned;
        /* LG fixed path checks the operand cursor (base+1), not F7 itself.
         * Explicit boundary expectations, not a copied pointer predicate. */
        if(!fr && !variable && (at==0x02021BFF || at==0x08B0FFFF ||
                               at==0x08BC0A3F || at==0x08DA8FFF))owned=1;
        unsigned ok=owned && gid<=0xAFF;
        input_byte(c,at,0xF7);input_byte(c,at+1,gid>>8);input_byte(c,at+2,gid);input_byte(c,at+3,0xFF);
        if(owned) {
            need(c->busRead8(c,at)==0xF7 && c->busRead8(c,at+1)==(gid>>8) &&
                 c->busRead8(c,at+2)==(gid&255),"synthetic stream readback");
        }
        for(unsigned k=0;k<96;k++) c->busWrite8(c,STACK-64+k,0xA5);
        set(c,"cpsr",0x3F);
        for(unsigned k=0;k<13;k++) {char name[8];snprintf(name,sizeof(name),"r%u",k);set(c,name,0x11110000u+k);}
        set(c,"r2",1);set(c,"r4",at);set(c,"r5",wrap?255:0);set(c,"r7",2);set(c,"r8",7);
        set(c,"sp",STACK);set(c,"lr",wrap?0x02030001:0x08001001);
        uint32_t entry=fr?(variable?0x087C006A:0x087C0048):(variable?0x08BC0036:0x08BC0000);
        set(c,"pc",entry);
        uint32_t want=variable?(ok?0x08005F6C:(fr?0x08005E82:0x08005E28)):(ok?0x08005D58:0x08005D4C);
        unsigned steps=0;uint32_t pc;
        while(steps++<1024) {
            pc=get(c,15)-2;
            if(pc==0x08005F6C || pc==0x08005E82 || pc==0x08005E28 || pc==0x08005D58 || pc==0x08005D4C)break;
            c->step(c);
        }
        need(steps<=1024,"bounded transfer");need(pc==want,"continuation target");
        unsigned width=gid==0x92F?0:(gid>=0x92A && gid<=0x92E?10:12);
        need(get(c,8)==7+(variable && ok?width:0),"width accumulator");
        need(get(c,4)==at+(variable && ok?2:0),"source advance");
        need(get(c,2)==1+(!variable && ok?2:0),"fixed token advance");
        unsigned glyphs=(wrap?255:0)+(!variable && ok?1:0);
        if(fr)glyphs&=255;
        need(get(c,5)==glyphs,"glyph count");need(get(c,13)==STACK,"stack restored");
        need(get(c,6)==0x11110006 && get(c,7)==2,"preserved r6/r7");
        for(unsigned k=9;k<12;k++)need(get(c,k)==0x11110000u+k,"preserved high register");
        for(unsigned k=0;k<16;k++) {
            need(c->busRead8(c,STACK-64+k)==0xA5,"lower canary");
            need(c->busRead8(c,STACK+k)==0xA5,"upper canary");
        }
        cases++;
    }
    c->deinit(c);free(rom);
    printf("{\"game\":\"%s\",\"cases\":%u,\"status\":\"SYNTHETIC_TRANSFERS_MATCH\","
           "\"native_continuations_executed\":false,\"game_font_or_save_input\":false,"
           "\"leafgreen_fallback_safe\":false,\"hardware_certified\":false}\n",argv[1],cases);
    return 0;
}
