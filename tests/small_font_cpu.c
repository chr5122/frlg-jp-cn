/* Generated-memory test; no game ROM, save, native assets or font files. */
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
#define STOP 0x0203D800u
#define FALLBACK 0x081DB3CAu
static void quiet(struct mLogger *l,int c,enum mLogLevel v,const char *f,va_list a)
{(void)l;(void)c;(void)v;(void)f;(void)a;}
static void need(int ok,const char *msg){if(!ok){fprintf(stderr,"FAIL: %s\n",msg);exit(1);}}
static void put(struct mCore*c,const char*n,uint32_t v){need(c->writeRegister(c,n,&v),"set register");}
static uint32_t get(struct mCore*c,unsigned k){char n[8];uint32_t v=0;snprintf(n,sizeof(n),"r%u",k);need(c->readRegister(c,n,&v),"get register");return v;}
static size_t load(const char *path,uint8_t *p,size_t cap)
{FILE*f=fopen(path,"rb");need(f!=NULL,"open generated input");size_t n=fread(p,1,cap,f);need(!ferror(f)&&fgetc(f)==EOF,"input size");fclose(f);return n;}
static void word(uint8_t*p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(v>>(8*i));}
int main(int argc,char **argv){
 need(argc==5,"usage: cpu decoder.bin stub.bin generated-dir expected.bin");
 uint8_t *rom=malloc(SIZE);need(rom!=NULL,"memory allocation");memset(rom,0xFF,SIZE);
 uint8_t code[128],stub[128],expected[6*64],widths[0xB00];
 need(load(argv[1],code,sizeof(code))==108,"decoder length");
 size_t n=load(argv[2],stub,sizeof(stub));need(n>0,"stub length");
 need(load(argv[4],expected,sizeof(expected))==sizeof(expected),"expected length");
 char path[2048];snprintf(path,sizeof(path),"%s/widths.bin",argv[3]);
 need(load(path,widths,sizeof(widths))==sizeof(widths),"width length");
 memcpy(rom+0x9D1400,code,108);memcpy(rom+0x2F5C,stub,n);memcpy(rom+0x9D08F0,widths,sizeof(widths));
 for(unsigned i=0;i<11;i++){
  uint32_t offset=0xA00000+i*0x4000;
  word(rom+0x9D08C0+4*i,0x08000000+offset);
  if(i==0||i==1||i==10){snprintf(path,sizeof(path),"%s/page_%02X.bin",argv[3],i);
   need(load(path,rom+offset,0x4000)==0x4000,"page length");}
 }
 struct mLogger l={.log=quiet};mLogSetDefaultLogger(&l);
 struct mCore*c=mCoreCreate(mPLATFORM_GBA);need(c&&c->init(c),"core init");mCoreInitConfig(c,NULL);
 struct VFile*vf=VFileFromConstMemory(rom,SIZE);need(vf&&c->loadROM(c,vf),"load synthetic ROM");c->reset(c);
 for(unsigned i=0;i<108;i++)c->busWrite8(c,RAM_CODE+i,code[i]);
 const unsigned ids[]={0,7,8,255,256,0xAFF};unsigned checks=0,fallbacks=0;
 for(unsigned mode=0;mode<2;mode++) for(unsigned test=0;test<8;test++){
  unsigned gid=test<6?ids[test]:test==6?0xB00:0x100;
  unsigned small=test==7?1:0;int expect_fallback=test>=6;
  for(unsigned i=0;i<128;i++)c->busWrite8(c,0x03003DE0+i,0xA5);
  c->busWrite8(c,0x03003E60,0xA5);c->busWrite8(c,0x03003E61,0xA5);
  for(unsigned i=0;i<96;i++)c->busWrite8(c,STACK-64+i,0xA5);
  put(c,"cpsr",0x3F);
  for(unsigned i=0;i<13;i++){char name[8];snprintf(name,sizeof(name),"r%u",i);put(c,name,0x11110000+i);}
  put(c,"r0",gid);put(c,"r1",small);put(c,"sp",STACK);put(c,"lr",STOP|1);
  put(c,"pc",mode?RAM_CODE:0x089D1400);
  unsigned steps=0;uint32_t pc=0;
  while(steps++<3000){pc=get(c,15)-2;if(pc==STOP||pc==FALLBACK)break;c->step(c);}
  need(steps<3000,"bounded execution");need(pc==(expect_fallback?FALLBACK:STOP),"return or fallback");
  need(get(c,13)==STACK,"SP restored");
  for(unsigned i=4;i<12;i++)need(get(c,i)==0x11110000+i,"callee-saved register");
  for(unsigned i=0;i<16;i++){need(c->busRead8(c,STACK-64+i)==0xA5,"lower stack canary");need(c->busRead8(c,STACK+i)==0xA5,"upper stack canary");}
  if(expect_fallback){
   for(unsigned i=0;i<128;i++)need(c->busRead8(c,0x03003DE0+i)==0xA5,"fallback does not draw");
   fallbacks++;continue;
  }
  for(unsigned tile=0;tile<4;tile++) for(unsigned i=0;i<32;i++){
   unsigned want=i<16?expected[test*64+tile*16+i]:0xA5;
   need(c->busRead8(c,0x03003DE0+tile*32+i)==want,"tile bytes");
  }
  need(c->busRead8(c,0x03003E60)==widths[gid],"width");
  need(c->busRead8(c,0x03003E61)==13,"height");checks++;
 }
 c->deinit(c);free(rom);
 printf("{\"status\":\"SYNTHETIC_CPU_PASS\",\"glyph_cases\":%u,\"fallback_cases\":%u,"
        "\"ram_relocation_tested\":true,\"game_font_or_save_input\":false,\"hardware_certified\":false}\n",checks,fallbacks);
 return 0;
}
