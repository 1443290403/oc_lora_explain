"""Portable ComfyUI graphs derived from the actual V6 full-body diagnostics."""
import copy

PROMPT='naikaer_oc, 1girl, solo, black dress, standing, full body,'
NEG='worst quality, low quality, bad anatomy, bad hands, text, watermark, signature, nsfw, nude'

def graph(s):
    g={
      '1':dict(class_type='CheckpointLoaderSimple',inputs=dict(ckpt_name=s.get('checkpoint','waiIllustriousSDXL_v170.safetensors'))),
      '3':dict(class_type='CLIPTextEncode',inputs=dict(text=s.get('prompt',PROMPT),clip=['1',1])),
      '4':dict(class_type='CLIPTextEncode',inputs=dict(text=s.get('negative',NEG),clip=['1',1])),
      '5':dict(class_type='EmptyLatentImage',inputs=dict(width=s.get('width',832),height=s.get('height',1216),batch_size=1)),
      '6':dict(class_type='KSampler',inputs=dict(model=['1',0],positive=['3',0],negative=['4',0],latent_image=['5',0],
           seed=s['seed'],steps=s.get('steps',28),cfg=s.get('cfg',5.5),sampler_name=s.get('sampler','dpmpp_2m_sde'),scheduler=s.get('scheduler','karras'),denoise=1.)),
      '7':dict(class_type='VAEDecode',inputs=dict(samples=['6',0],vae=['1',2])),
      '8':dict(class_type='SaveImage',inputs=dict(images=['7',0],filename_prefix='oc_lora_evaluation/'+s['name']))}
    if s.get('lora'):
      g['2']=dict(class_type='LoraLoader',inputs=dict(model=['1',0],clip=['1',1],lora_name=s['lora'],strength_model=s['strength'],strength_clip=1.))
      g['3']['inputs']['clip']=['2',1];g['4']['inputs']['clip']=['2',1];g['6']['inputs']['model']=['2',0]
    if s.get('mode') in ['latent_hires','pixel_hires']:
      if s['mode']=='latent_hires':
        g['9']=dict(class_type='LatentUpscaleBy',inputs=dict(samples=['6',0],upscale_method='bislerp',scale_by=1.5))
        latent=['9',0]
      else:
        g['9']=dict(class_type='ImageScale',inputs=dict(image=['7',0],upscale_method='lanczos',width=1248,height=1824,crop='disabled'))
        g['10']=dict(class_type='VAEEncode',inputs=dict(pixels=['9',0],vae=['1',2]));latent=['10',0]
      g['11']=copy.deepcopy(g['6']);g['11']['inputs'].update(latent_image=latent,steps=s.get('refine_steps',16),denoise=s.get('denoise',.35 if s['mode']=='latent_hires' else .30))
      g['12']=dict(class_type='VAEDecode',inputs=dict(samples=['11',0],vae=['1',2]));g['8']['inputs']['images']=['12',0]
    assert 'artist:' not in g['3']['inputs']['text']
    return g
