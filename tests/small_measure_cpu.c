/* Synthetic source stream and metric callbacks; no game/ROM/save/font input. */
#include <mgba/core/core.h>
#include <mgba/core/log.h>
#include <mgba-util/vfs.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define SIZE 0x1000000u
#define STACK 0x03007E00u
#define RAM_CODE 0x0203E000u
#define STREAM 0x02008000u
#define STOP 0x0203D800u
static void quiet(struct mLogger*l,int c,enum mLogLevel v,const char*f,va_list a)
{(void)l;(void)c;(void)v;(void)f;(void)a;}
static void need(int ok,const char*m){if(!ok){fprintf(stderr,"FAIL: %s\n",m);exit(1);}}
static void put(struct mCore*c,const char*n,uint32_t v){need(c->writeRegister(c,n,&v),"set register");}
static uint32_t get(struct mCore*c,unsigned k){char n[8];uint32_t v=0;snprintf(n,sizeof(n),"r%u",k);need(c->readRegister(c,n,&v),"get register");return v;}
static size_t load(const char*path,uint8_t*p,size_t cap)
{FILE*f=fopen(path,"rb");need(f!=NULL,"open generated input");size_t n=fread(p,1,cap,f);need(!ferror(f)&&fgetc(f)==EOF,"input size");fclose(f);return n;}
struct input {uint8_t bytes[16];unsigned size,expected;};
static const struct input cases[]={
 {{0xFF},1,0},{{1,0,0,0xFF},4,5},{{0,1,0,2,0xFF},5,19},
 {{0xF7,1,0,0xFF},4,10},{{0xF7,1,0xFF,0xFF},4,11},{{0xF7,9,0x2F,0xFF},4,0},
 {{0xF8,2,0,0xFF},4,10},{{1,0xFC,0x0D,2,2,0xFF},6,8},
 {{1,0xFC,0x0D,30,0,0xFF},6,5},{{0xF7,0x0A,0xFF,0xF8,0,0xFF},6,20},
 {{0xFC,0x0D,16,0xF7,1,0,0,0xFF},8,26},{{2,0xFF},2,6}};
int main(int argc,char**argv){
 need(argc==5,"usage: cpu fr|lg code callbacks good|bad");int fr=!strcmp(argv[1],"fr");need(fr||!strcmp(argv[1],"lg"),"profile");
 int bad=!strcmp(argv[4],"bad");need(bad||!strcmp(argv[4],"good"),"variant");
 uint8_t*rom=malloc(SIZE);need(rom!=NULL,"memory allocation");memset(rom,0xFF,SIZE);
 uint8_t code[128],cb[128];need(load(argv[2],code,sizeof(code))==120,"measure length");size_t n=load(argv[3],cb,sizeof(cb));need(n>0,"callbacks");
 uint32_t offset=fr?0x7B8450:0x6D5048;memcpy(rom+offset,code,120);memcpy(rom+0x6294,cb,n);
 uint32_t wt=fr?0x9D08D0:0x9D08F0;memset(rom+wt,0,0xB00);
 rom[wt+0x100]=bad?9:10;rom[wt+0x1FF]=11;rom[wt+0x92F]=0;rom[wt+0xAFF]=12;
 struct mLogger l={.log=quiet};mLogSetDefaultLogger(&l);struct mCore*c=mCoreCreate(mPLATFORM_GBA);
 need(c&&c->init(c),"init");mCoreInitConfig(c,NULL);struct VFile*vf=VFileFromConstMemory(rom,SIZE);need(vf&&c->loadROM(c,vf),"load synthetic");c->reset(c);
 for(unsigned i=0;i<120;i++)c->busWrite8(c,RAM_CODE+i,code[i]);unsigned done=0;
 for(unsigned mode=0;mode<2;mode++)for(unsigned test=0;test<sizeof(cases)/sizeof(*cases);test++){
  for(unsigned i=0;i<cases[test].size;i++)c->busWrite8(c,STREAM+i,cases[test].bytes[i]);
  for(unsigned i=0;i<96;i++)c->busWrite8(c,STACK-64+i,0xA5);
  put(c,"cpsr",0x3F);for(unsigned i=0;i<13;i++){char name[8];snprintf(name,sizeof(name),"r%u",i);put(c,name,0x11110000+i);}
  put(c,"r0",STREAM);put(c,"sp",STACK);put(c,"lr",STOP|1);put(c,"pc",mode?RAM_CODE:0x08000000+offset);
  unsigned steps=0;while(get(c,15)-2!=STOP&&steps++<4000)c->step(c);
  need(steps<4000,"bounded return");need(get(c,0)==cases[test].expected,"width result");need(get(c,13)==STACK,"stack restored");
  for(unsigned i=4;i<12;i++)need(get(c,i)==0x11110000+i,"callee-saved registers");
  for(unsigned i=0;i<16;i++){need(c->busRead8(c,STACK-64+i)==0xA5,"lower canary");need(c->busRead8(c,STACK+i)==0xA5,"upper canary");}done++;
 }
 c->deinit(c);free(rom);printf("{\"cases\":%u,\"ram_relocation_tested\":true}\n",done);return 0;
}
