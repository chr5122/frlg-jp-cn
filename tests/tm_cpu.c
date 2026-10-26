/* Project-owned synthetic mGBA CPU test. No game ROM, save or font input. */
#include <mgba/core/core.h>
#include <mgba/core/log.h>
#include <mgba-util/vfs.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define ROM_SIZE 0x1000000
#define OBJECT 0x02008000u
#define OBJECT_SIZE 0x28D4u
#define STACK 0x03007E00u
#define RAM_ENTRY 0x0203E000u
#define TABLE 0x0871F444u
#define CODE 0x08ED9400u

static void quiet(struct mLogger *logger, int category, enum mLogLevel level,
                  const char *format, va_list args) {
    (void)logger; (void)category; (void)level; (void)format; (void)args;
}
static void need(int ok, const char *label) {
    if (!ok) { fprintf(stderr, "FAIL: %s\n", label); exit(1); }
}
static uint32_t reg(struct mCore *c, unsigned index) {
    char name[8]; uint32_t value=0;
    snprintf(name,sizeof(name),"r%u",index);
    need(c->readRegister(c,name,&value),"read register"); return value;
}
static void setreg(struct mCore *c, const char *name, uint32_t value) {
    need(c->writeRegister(c,name,&value),"write register");
}
static void word(uint8_t *p, uint32_t value) {
    for (int i=0;i<4;i++) p[i]=(uint8_t)(value>>(i*8));
}
static void veneer(uint8_t *p, uint32_t target) {
    const uint8_t instructions[4]={0x00,0x4b,0x18,0x47};
    memcpy(p,instructions,4);word(p+4,target|1);
}
static size_t load(const char *path, uint8_t *out, size_t limit) {
    FILE *f=fopen(path,"rb");need(f!=NULL,"open own compiled payload");
    size_t n=fread(out,1,limit,f);need(!ferror(f) && fgetc(f)==EOF,"payload size/read");
    fclose(f);return n;
}
static unsigned run(struct mCore *c, uint32_t entry, uint32_t stop,
                    uint32_t r0, uint32_t r1, uint32_t r2, uint32_t lr) {
    for (unsigned i=0;i<OBJECT_SIZE;i++) c->busWrite8(c,OBJECT+i,0xCC);
    for (unsigned i=0;i<96;i++) c->busWrite8(c,STACK-80+i,0xA5);
    uint32_t status=0x3F; /* System mode, Thumb; synthetic execution only. */
    setreg(c,"cpsr",status);
    for (unsigned i=0;i<13;i++) {
        char name[8];snprintf(name,sizeof(name),"r%u",i);
        uint32_t value=(i==4 || i==6)?OBJECT:0x11110000u+i;
        setreg(c,name,value);
    }
    setreg(c,"r0",r0);setreg(c,"r1",r1);setreg(c,"r2",r2);
    setreg(c,"sp",STACK);setreg(c,"lr",lr);setreg(c,"pc",entry);
    unsigned copies=0,steps=0;
    /* mGBA Thumb PC reads are current instruction+2 (verified on 0.10.5). */
    while (reg(c,15)-2!=stop && steps++<1000) {
        if (reg(c,15)-2==0x08008900u) copies++;
        c->step(c);
    }
    need(steps<=1000,"bounded return");need(reg(c,13)==STACK,"SP restored");
    for (unsigned i=4;i<12;i++)
        need(reg(c,i)==((i==4 || i==6)?OBJECT:0x11110000u+i),"callee-saved register");
    for (unsigned i=0;i<16;i++) {
        need(c->busRead8(c,STACK-80+i)==0xA5,"lower stack canary");
        need(c->busRead8(c,STACK+i)==0xA5,"upper stack canary");
    }
    return copies;
}

int main(int argc, char **argv) {
    need(argc==3,"usage: tm_cpu routes.bin synthetic_copy.bin");
    uint8_t *rom=malloc(ROM_SIZE);need(rom!=NULL,"allocate synthetic ROM");
    memset(rom,0xFF,ROM_SIZE);
    uint8_t payload[100],copy[100];
    need(load(argv[1],payload,sizeof(payload))==96,"96-byte mature routes");
    size_t copy_size=load(argv[2],copy,sizeof(copy));need(copy_size>0,"synthetic copier");
    memcpy(rom+0xED9400,payload,96);memcpy(rom+0x8900,copy,copy_size);
    /* Synthetic task-object getter: LDR r0,[pc]; BX lr; .word OBJECT. */
    const uint8_t getter[4]={0x00,0x48,0x70,0x47};
    memcpy(rom+0x11D8B0,getter,4);word(rom+0x11D8B4,OBJECT);
    const uint32_t sites[4]={0x11CDD0,0x11CF00,0x11D8F4,0x11D900};
    const uint32_t targets[4]={CODE+0x18,CODE+0x30,CODE,CODE+4};
    for (unsigned i=0;i<4;i++) veneer(rom+sites[i],targets[i]);
    uint8_t lengths[355];
    for (unsigned i=0;i<355;i++) {
        unsigned symbols=1+i%5;uint8_t *p=rom+0x71F444+i*16;
        for (unsigned j=0;j<symbols;j++) {p[j*3]=0xF7;p[j*3+1]=0;p[j*3+2]=1+j;}
        p[symbols*3]=255;lengths[i]=(uint8_t)(symbols*3+1);
    }
    struct mLogger logger={.log=quiet};mLogSetDefaultLogger(&logger);
    struct mCore *c=mCoreCreate(mPLATFORM_GBA);need(c && c->init(c),"mGBA init");
    mCoreInitConfig(c,NULL);
    struct VFile *vf=VFileFromConstMemory(rom,ROM_SIZE);
    need(vf && c->loadROM(c,vf),"load synthetic memory ROM");c->reset(c);
    unsigned writer_cases=0,getter_cases=0;
    for (unsigned mode=0;mode<2;mode++) for (unsigned kind=0;kind<2;kind++) {
        uint32_t entry=0x08000000u+sites[kind];
        if (mode) {
            for (unsigned i=0;i<8;i++) c->busWrite8(c,RAM_ENTRY+i,rom[sites[kind]+i]);
            entry=RAM_ENTRY;
        }
        for (unsigned name=0;name<355;name++) {
            uint32_t stop=kind?0x0811CF08u:0x0811CDD8u;
            unsigned copies=run(c,entry,stop,OBJECT+(kind?0x7F:0x77),name*16,TABLE,
                                (name%2)?0x0811CDD7u:0x0231CDD7u);
            need(copies==1,"writer performs exactly one copy");
            unsigned start=kind?0x1D0:0x1C0;
            for (unsigned i=0;i<OBJECT_SIZE;i++) {
                uint8_t expected=(i>=start && i<start+lengths[name])?
                    rom[0x71F444+name*16+i-start]:0xCC;
                need(c->busRead8(c,OBJECT+i)==expected,"exact writer buffer and object canary");
            }
            if (!kind) need(reg(c,0)==OBJECT,"forgotten writer returns object");
            writer_cases++;
        }
    }
    const uint32_t callers[4]={0x0811CDD7u,0x0811CF09u,0x0231CDD7u,0x08ED9F01u};
    for (unsigned mode=0;mode<2;mode++) for (unsigned kind=0;kind<2;kind++) {
        uint32_t entry=0x08000000u+sites[kind+2];
        if (mode) {
            for (unsigned i=0;i<8;i++) c->busWrite8(c,RAM_ENTRY+i,rom[sites[kind+2]+i]);
            entry=RAM_ENTRY;
        }
        for (unsigned k=0;k<4;k++) {
            need(run(c,entry,callers[k]&~1u,7,8,9,callers[k])==0,"getter must never copy");
            need(reg(c,0)==OBJECT+(kind?0x1D0:0x1C0),"getter returns own buffer");
            for (unsigned i=0;i<OBJECT_SIZE;i++) need(c->busRead8(c,OBJECT+i)==0xCC,"getter object read-only");
            getter_cases++;
        }
    }
    c->deinit(c);free(rom);
    printf("{\"status\":\"PASS\",\"writer_cases\":%u,\"getter_cases\":%u,"
           "\"synthetic_copy_and_object_lookup\":true,\"ram_entry_executed\":true,"
           "\"hardware_certified\":false,\"game_or_save_input\":false}\n",writer_cases,getter_cases);
    return 0;
}
