"""Run an explicit OneTrainer config; record progress and validate final tensors.

Use the OneTrainer Python environment, not the lightweight helper environment.
"""
import argparse
import sys,os,json,time,threading,subprocess,traceback
from pathlib import Path
from project_paths import path_for


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config",type=Path)
    parser.add_argument("--onetrainer",type=Path)
    args=parser.parse_args()
    repo=(args.onetrainer or path_for("onetrainer")).resolve()
    if not (repo/"modules").is_dir():
        parser.error("Set the OneTrainer directory in configs/local.toml or --onetrainer")
    config_path=args.config.resolve();run=config_path.parent
    os.chdir(repo);sys.path.insert(0,str(repo))
    import torch,psutil
    from modules.util import create
    from modules.util.config.TrainConfig import TrainConfig
    from modules.util.callbacks.TrainCallbacks import TrainCallbacks
    from modules.util.commands.TrainCommands import TrainCommands
    cfg=TrainConfig.default_values().from_dict(json.loads(config_path.read_text(encoding='utf-8')))
    assert not Path(cfg.output_model_destination).exists(), 'Refusing to overwrite an existing final LoRA'
    stats={'config':str(config_path),'torch':torch.__version__,'gpu':torch.cuda.get_device_name(0),'completed':False,'steps':0,'epoch':0,'max_total_gpu_used_mib':0,'max_process_ram_gib':0,'stages':[]}
    stop=threading.Event();started=time.time();last_status=None
    def write_status():
        stats['elapsed_s']=round(time.time()-started,2)
        tmp=run/'progress.tmp'
        tmp.write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(tmp,run/'progress.json')
    def monitor():
        while not stop.is_set():
            try:
                n=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                stats['max_total_gpu_used_mib']=max(stats['max_total_gpu_used_mib'],int(n.strip().splitlines()[0]))
                stats['max_process_ram_gib']=max(stats['max_process_ram_gib'],psutil.Process().memory_info().rss/2**30)
            except Exception:pass
            stop.wait(1)
    def status(s):
        nonlocal last_status
        if s!=last_status:
            stats['stages'].append({'elapsed_s':round(time.time()-started,1),'status':s})
            print('STATUS:',s,flush=True);last_status=s;write_status()
    def progress(p,*_):
        stats['steps']=p.global_step;stats['epoch']=p.epoch;stats['epoch_step']=p.epoch_step
        if p.global_step%10==0:write_status()
    thread=threading.Thread(target=monitor,daemon=True);thread.start()
    try:
        trainer=create.create_trainer(cfg,TrainCallbacks(on_update_status=status,on_update_train_progress=progress),TrainCommands())
        trainer.start()
        if cfg.lora_model_name and Path(cfg.lora_model_name).is_file():
            from safetensors.torch import load_file
            from modules.modelLoader.mixin.LoRALoaderMixin import LoRALoaderMixin
            expected=LoRALoaderMixin()._to_canonical(trainer.model,load_file(cfg.lora_model_name,device='cpu'))
            actual={}
            for adapter in trainer.model.adapters():actual.update(adapter.state_dict())
            assert set(actual)==set(expected), 'Loaded adapter keys do not match requested LoRA'
            mismatches=[k for k in expected if not torch.equal(actual[k].detach().cpu().float(),expected[k].float())]
            assert not mismatches, f'Loaded adapter differs from requested LoRA: {mismatches[:5]}'
            stats['initial_lora_verified']=cfg.lora_model_name
            stats['initial_lora_tensor_count']=len(expected)
            print('Initial LoRA verified against input file:',cfg.lora_model_name,flush=True)
            del actual,expected
        trainer.train();trainer.end()
        from safetensors import safe_open
        output=Path(cfg.output_model_destination)
        with safe_open(str(output),framework='pt',device='cpu') as f:
            keys=list(f.keys());bad=[k for k in keys if not torch.isfinite(f.get_tensor(k)).all().item()]
        assert keys and not bad, f'Invalid output tensors: {bad}'
        stats.update(completed=True,output=str(output),output_size_mib=round(output.stat().st_size/2**20,2),tensor_count=len(keys),nonfinite_tensors=bad)
    except Exception as e:
        stats['error']=repr(e);traceback.print_exc()
    finally:
        stats['torch_peak_allocated_mib']=round(torch.cuda.max_memory_allocated()/2**20,1)
        stats['torch_peak_reserved_mib']=round(torch.cuda.max_memory_reserved()/2**20,1)
        stop.set();thread.join(timeout=3);write_status()
        (run/'result.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(stats,ensure_ascii=False),flush=True)
    if not stats['completed']:sys.exit(1)


if __name__=="__main__":
    main()
