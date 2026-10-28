/* Generated memory only. Execute the real wrapper AND measurer, stop at the
 * native summary continuation. No native drawing/game/font/save input. */
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
#define WINDOWS 0x02020430u
static void quiet(struct mLogger*l,int c,enum mLogLevel v,const char*f,va_list a)
{(void)l;(void)c;(void)v;(void)f;(void)a;}
static void need(int ok,const char*m){if(!ok){fprintf(stderr,"FAIL: %s\n",m);exit(1);}}
static void put(struct mCore*c,const char*n,uint32_t v){need(c->writeRegister(c,n,&v),"set register");}
static uint32_t get(struct mCore*c,unsigned k){char n[8];uint32_t v=0;snprintf(n,sizeof(n),"r%u",k);need(c->readRegister(c,n,&v),"get register");return v;}
static size_t load(const char*path,uint8_t*p,size_t cap)
{FILE*f=fopen(path,"rb");need(f!=NULL,"open generated input");size_t n=fread(p,1,cap,f);need(!ferror(f)&&fgetc(f)==EOF,"input size");fclose(f);return n;}
struct input {uint8_t bytes[16];unsigned size,extent;};
static const struct input cases[]={
 {{0xFF},1,0},{{1,0,0,0xFF},4,5},{{0,1,0,2,0xFF},5,19},
 {{0xF7,1,0,0xFF},4,10},{{0xF7,1,0xFF,0xFF},4,11},{{0xF7,9,0x2F,0xFF},4,0},
 {{0xF8,2,0,0xFF},4,10},{{1,0xFC,0x0D,2,2,0xFF},6,8},
 {{1,0xFC,0x0D,30,0,0xFF},6,5},{{0xF7,0x0A,0xFF,0xF8,0,0xFF},6,20},
 {{0xFC,0x0D,16,0xF7,1,0,0,0xFF},8,26},{{2,0xFF},2,6}};
static const unsigned layouts[][2]={{0,30},{0,28},{10,20},{20,10},{29,1},{2,4}};
int main(int argc,char**argv){
 need(argc==6,"usage: cpu fr|lg wrapper measure callbacks good|bad-width|bad-tail");
 int fr=!strcmp(argv[1],"fr");need(fr||!strcmp(argv[1],"lg"),"profile");
 int badwidth=!strcmp(argv[5],"bad-width"),badtail=!strcmp(argv[5],"bad-tail");
 need(badwidth||badtail||!strcmp(argv[5],"good"),"variant");
 uint8_t*rom=malloc(SIZE);need(rom!=NULL,"memory allocation");memset(rom,0xFF,SIZE);
 uint8_t wrapper[72],measure[120],cb[128];need(load(argv[2],wrapper,sizeof(wrapper))==72,"wrapper size");need(load(argv[3],measure,sizeof(measure))==120,"measure size");size_t n=load(argv[4],cb,sizeof(cb));need(n>0,"callbacks");
 uint32_t mo=fr?0x7B8450:0x6D5048,wo=fr?0x7B84C8:0x6D5000,tail=fr?0x081375F0:0x081375C8;
 if(badtail)wrapper[68]^=2; /* Wrong continuation must not be accepted. */
 memcpy(rom+wo,wrapper,72);memcpy(rom+mo,measure,120);memcpy(rom+0x6294,cb,n);
 uint32_t wt=fr?0x9D08D0:0x9D08F0;memset(rom+wt,0,0xB00);rom[wt+0x100]=badwidth?9:10;rom[wt+0x1FF]=11;rom[wt+0xAFF]=12;
 struct mLogger l={.log=quiet};mLogSetDefaultLogger(&l);struct mCore*c=mCoreCreate(mPLATFORM_GBA);need(c&&c->init(c),"init");mCoreInitConfig(c,NULL);struct VFile*vf=VFileFromConstMemory(rom,SIZE);need(vf&&c->loadROM(c,vf),"load generated ROM");c->reset(c);
 uint32_t low=mo<wo?mo:wo;
 for(unsigned i=0;i<72;i++)c->busWrite8(c,RAM_CODE+wo-low+i,wrapper[i]);
 for(unsigned i=0;i<120;i++)c->busWrite8(c,RAM_CODE+mo-low+i,measure[i]);
 unsigned done=0;
 for(unsigned mode=0;mode<2;mode++)for(unsigned layout=0;layout<6;layout++)for(unsigned test=0;test<12;test++){
  unsigned window=(layout+test)%8,left=layouts[layout][0]*8,width=layouts[layout][1]*8;
  unsigned edge=left+width<236?left+width:236,space=edge-left;
  unsigned expected=cases[test].extent<=space?space-cases[test].extent:8;
  for(unsigned i=0;i<cases[test].size;i++)c->busWrite8(c,STREAM+i,cases[test].bytes[i]);
  for(unsigned i=0;i<144;i++)c->busWrite8(c,STACK-96+i,0xA5);
  for(unsigned i=0;i<96;i++)c->busWrite8(c,WINDOWS+i,0);
  c->busWrite8(c,WINDOWS+window*12+1,layouts[layout][0]);c->busWrite8(c,WINDOWS+window*12+3,layouts[layout][1]);
  put(c,"cpsr",0x3F);for(unsigned i=0;i<13;i++){char name[8];snprintf(name,sizeof(name),"r%u",i);put(c,name,0x11110000+i);}
  uint32_t lr=0x0203D801+4*(test%5);put(c,"r0",window);put(c,"r6",STREAM);put(c,"sp",STACK);put(c,"lr",lr);put(c,"pc",mode?RAM_CODE+wo-low:0x08000000+wo);
  unsigned steps=0;while(get(c,15)-2!=tail&&steps++<6000)c->step(c);
  need(steps<6000,"bounded native continuation");need(get(c,2)==expected,"alignment result");need(get(c,0)==window&&get(c,1)==0,"printer arguments");need(get(c,13)==STACK&&get(c,14)==lr,"native stack/LR contract");
  for(unsigned i=4;i<12;i++)need(get(c,i)==(i==6?STREAM:0x11110000+i),"preserved registers");
  need(c->busRead32(c,STACK)==0xA5A5A5A5u&&c->busRead32(c,STACK+4)==0&&c->busRead32(c,STACK+8)==STREAM,"stack printer arguments");
  for(unsigned i=0;i<16;i++){need(c->busRead8(c,STACK-96+i)==0xA5,"lower canary");need(c->busRead8(c,STACK+12+i)==0xA5,"upper canary");}done++;
 }
 c->deinit(c);free(rom);printf("{\"cases\":%u,\"ram_relocation_tested\":true,\"native_drawing_executed\":false}\n",done);return 0;
}
