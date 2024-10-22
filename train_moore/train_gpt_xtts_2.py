import os

import torch
from trainer import Trainer, TrainerArgs

from TTS.config.shared_configs import BaseDatasetConfig
from TTS.tts.datasets import load_tts_samples
from TTS.tts.layers.xtts.trainer.gpt_trainer import GPTArgs, GPTTrainer, GPTTrainerConfig, XttsAudioConfig
from TTS.utils.manage import ModelManager
from moore_training_utils import MooreGPTTrainer, moore_dataset_formatter, build_reference_audios_dict

# Logging parameters
RUN_NAME = "RUN_GPT_XTTS_v2.0_MOS_FT_1"
PROJECT_NAME = "MOS_FINE_TUNING_1"
DASHBOARD_LOGGER = "tensorboard"
LOGGER_URI = None
LANGUAGE="mos"

# Set here the path that the checkpoints will be saved. Default: ./run/training/
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run", "training")

# Training Parameters
OPTIMIZER_WD_ONLY_ON_WEIGHTS = False  # for multi-gpu training please make it False
START_WITH_EVAL = True  # if True it will star with evaluation
BATCH_SIZE = 16  # set here the batch size
GRAD_ACUMM_STEPS = 21  # set here the grad accumulation steps
# Note: we recommend that BATCH_SIZE * GRAD_ACUMM_STEPS need to be at least 252 for more efficient training. You can increase/decrease BATCH_SIZE but then set GRAD_ACUMM_STEPS accordingly.

# Define here the dataset that you want to use for the fine-tuning on.
config_dataset = BaseDatasetConfig(
    formatter=moore_dataset_formatter,
    dataset_name="sentences-audio-texte-denoised-enhanced",
    path="/teamspace/studios/this_studio/coqui-TTS/train_moore/dataset",
    meta_file_train="/teamspace/studios/this_studio/coqui-TTS/train_moore/dataset/metadata.txt",
    meta_file_val="/teamspace/studios/this_studio/coqui-TTS/train_moore/dataset/metadata_val.txt",
)

# Add here the configs of the datasets
DATASETS_CONFIG_LIST = [config_dataset]

# Define the path where XTTS v2.0.1 files will be downloaded
CHECKPOINTS_OUT_PATH = os.path.join(OUT_PATH, "CHECKPOINT_GPT_XTTS_v2.0_MOS_FT_1/")
os.makedirs(CHECKPOINTS_OUT_PATH, exist_ok=True)

# DVAE files
DVAE_CHECKPOINT_LINK = "https://huggingface.co/ArissBandoss/coqui-tts-moore-V1/resolve/main/dvae.pth"
MEL_NORM_LINK = "https://huggingface.co/ArissBandoss/coqui-tts-moore-V1/resolve/main/mel_stats.pth"

# Set the path to the downloaded files
DVAE_CHECKPOINT = os.path.join(CHECKPOINTS_OUT_PATH, os.path.basename(DVAE_CHECKPOINT_LINK))
MEL_NORM_FILE = os.path.join(CHECKPOINTS_OUT_PATH, os.path.basename(MEL_NORM_LINK))

# download DVAE files if needed
if not os.path.isfile(DVAE_CHECKPOINT) or not os.path.isfile(MEL_NORM_FILE):
    print(" > Downloading DVAE files!")
    ModelManager._download_model_files([MEL_NORM_LINK, DVAE_CHECKPOINT_LINK], CHECKPOINTS_OUT_PATH, progress_bar=True)

# Download XTTS v2.0 checkpoint if needed
TOKENIZER_FILE_LINK = "https://huggingface.co/ArissBandoss/coqui-tts-moore-V1/resolve/main/vocab.json"
XTTS_CHECKPOINT_LINK = "https://huggingface.co/ArissBandoss/coqui-tts-moore-V1/resolve/main/model.pth"

# XTTS transfer learning parameters: You we need to provide the paths of XTTS model checkpoint that you want to do the fine tuning.
TOKENIZER_FILE = os.path.join(CHECKPOINTS_OUT_PATH, os.path.basename(TOKENIZER_FILE_LINK))  # vocab.json file
#TOKENIZER_FILE = "/teamspace/studios/this_studio/coqui-TTS-V2/finetuning/bambara/saved/vocab.json"  # vocab.json file
XTTS_CHECKPOINT = os.path.join(CHECKPOINTS_OUT_PATH, os.path.basename(XTTS_CHECKPOINT_LINK))  # model.pth file

# download XTTS v2.0 files if needed
if not os.path.isfile(XTTS_CHECKPOINT):
    print(" > Downloading XTTS v2.0 files!")
    ModelManager._download_model_files(
        [TOKENIZER_FILE_LINK, XTTS_CHECKPOINT_LINK], CHECKPOINTS_OUT_PATH, progress_bar=True
    )

# Training sentences generations
# speaker reference to be used in training test sentences
#SPEAKER_REFERENCES = build_reference_audios_dict("./reference_audios")
SPEAKER_REFERENCE = [
    "/teamspace/studios/this_studio/coqui-TTS/train_moore/reference_speaker_male_1.wav"  # speaker reference to be used in training test sentences
]

def main():
    # init args and config
    model_args = GPTArgs(
        max_conditioning_length=132300,  # 6 secs
        min_conditioning_length=66150,  # 3 secs
        debug_loading_failures=False,
        max_wav_length=255995,  # ~11.6 seconds
        max_text_length=200,
        gpt_loss_text_ce_weight=0.01,
        gpt_loss_mel_ce_weight=1.5,
        mel_norm_file=MEL_NORM_FILE,
        dvae_checkpoint=DVAE_CHECKPOINT,
        xtts_checkpoint=XTTS_CHECKPOINT,  # checkpoint path of the model that you want to fine-tune
        tokenizer_file=TOKENIZER_FILE,
        gpt_num_audio_tokens=1026,
        gpt_start_audio_token=1024,
        gpt_stop_audio_token=1025,
        gpt_use_masking_gt_prompt_approach=True,
        gpt_use_perceiver_resampler=True
    )
    # define audio config
    audio_config = XttsAudioConfig(sample_rate=22050, dvae_sample_rate=22050, output_sample_rate=24000)
    # training parameters config
    config = GPTTrainerConfig(
        epochs=50,
        output_path=OUT_PATH,
        model_args=model_args,
        run_name=RUN_NAME,
        project_name=PROJECT_NAME,
        run_description="""
            GPT XTTS training
            """,
        dashboard_logger=DASHBOARD_LOGGER,
        logger_uri=LOGGER_URI,
        audio=audio_config,
        batch_size=BATCH_SIZE,
        batch_group_size=48,
        eval_batch_size=BATCH_SIZE,
        num_loader_workers=8,
        eval_split_max_size=256,
        print_step=100,
        plot_step=100,
        log_model_step=1194,
        save_step=10000,
        save_n_checkpoints=1,
        save_checkpoints=True,
        # target_loss="loss",
        print_eval=False,
        mixed_precision=True,
        use_grad_scaler=True,
        grad_clip=7.0,
        # Optimizer values like tortoise, pytorch implementation with modifications to not apply WD to non-weight parameters.
        optimizer="AdamW",
        optimizer_wd_only_on_weights=OPTIMIZER_WD_ONLY_ON_WEIGHTS,
        optimizer_params={"betas": [0.9, 0.96], "eps": 1e-8, "weight_decay": 1e-2, "fused": True},
        lr=1e-05,  # learning rate
        # lr_scheduler="MultiStepLR",
        lr_scheduler="ExponentialLR",
        warmup_steps=1193 * 3,
        warmup_start_lr=0.1,
        # it was adjusted accordly for the new step scheme
        # lr_scheduler_params={"milestones": [50000 * 18, 150000 * 18, 300000 * 18], "gamma": 0.5, "last_epoch": -1},
        lr_scheduler_params={"gamma": 0.01, "last_epoch": -1},
        sound_norm_refs=True,
        languages=["mos"],
        #distributed_url="tcp://127.0.0.1:54321",
        test_sentences=[
            {
                "text": "A vẽkembeoogo, Amélie sẽ da kẽnde weeoga pʋga, a wʋma koɛɛga n boaala.",
                "speaker_wav": SPEAKER_REFERENCE,
                "language": LANGUAGE,
            },
            {
                "text": "Nug tʋmtʋmdba wʋgda pɛɛla tare kõbgo.",
                "speaker_wav": SPEAKER_REFERENCE,
                "language": LANGUAGE,
            },
        ],
    )

    # init the model from config
    model = GPTTrainer.init_from_config(config)
    # model = torch.compile(model, fullgraph=True)

    # load training samples
    train_samples, eval_samples = load_tts_samples(
        DATASETS_CONFIG_LIST,
        eval_split=True,
        formatter=moore_dataset_formatter,
        eval_split_max_size=config.eval_split_max_size,
        eval_split_size=config.eval_split_size,
    )

    # init the trainer and 🚀
    trainer = Trainer(
        TrainerArgs(
            restore_path=None,
            # xtts checkpoint is restored via xtts_checkpoint key so no need of restore it using Trainer restore_path parameter
            skip_train_epoch=False,
            start_with_eval=START_WITH_EVAL,
            grad_accum_steps=GRAD_ACUMM_STEPS,
            use_accelerate=False,
        ),
        config,
        output_path=OUT_PATH,
        model=model,
        train_samples=train_samples,
        eval_samples=eval_samples,
    )
    trainer.fit()


if __name__ == "__main__":
    main()