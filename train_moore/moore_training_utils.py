import os
import re
from typing import List, Union, Dict

import torch
from tokenizers import Tokenizer
from TTS.tts.layers.xtts.trainer.gpt_trainer import GPTTrainer
from coqpit import Coqpit
from tqdm import tqdm
from types import NoneType


def build_reference_audios_dict(directory):
    """
    Builds a dictionary with language codes as keys. Each key contains a list of lists of audio files,
    where each list corresponds to a different speaker within that language.

    Args:
    directory (str): The root directory containing language code subdirectories and speaker directories.

    Returns:
    dict: A dictionary with language codes as keys and a list of lists of audio file paths as values.
    """
    audio_dict = {}

    # Iterate over each language code directory in the root directory
    for lang_code in os.listdir(directory):
        lang_path = os.path.join(directory, lang_code)
        if os.path.isdir(lang_path):  # Ensure it's a directory
            speakers_files = []  # List to hold lists of files for each speaker in this language

            # Iterate over each speaker directory within the language code directory
            for speaker in os.listdir(lang_path):
                speaker_path = os.path.join(lang_path, speaker)
                if os.path.isdir(speaker_path):  # Ensure it's a directory
                    # List all audio files in the speaker directory
                    speaker_files = [os.path.join(speaker_path, f) for f in os.listdir(speaker_path) if f.endswith('.wav')]
                    speakers_files.append(speaker_files)

            audio_dict[lang_code] = speakers_files

    return audio_dict


def moore_dataset_formatter(root_path, meta_file, **kwargs):  # pylint: disable=unused-argument
    """Normalizes the LJSpeech meta data file to TTS format
    https://keithito.com/LJ-Speech-Dataset/"""
    txt_file = os.path.join(root_path, meta_file)
    items = []
    with open(txt_file, "r", encoding="utf-8") as ttf:
        for line in tqdm(ttf):
            cols = line.split("|")
            wav_file = os.path.join(root_path, "wavs", cols[0] + ".wav")
            text = cols[2]
            speaker_name = f"speaker_{cols[3]}".replace("\n", "")
            lang = f"{cols[4]}".replace("\n", "") if len(cols) > 4  else 'mos'
            items.append({"text": text, "audio_file": wav_file, "speaker_name": speaker_name, "language": lang, "root_path": root_path})
    return items


class VoiceMooreTextPreprocessor:
    def preprocess_batch(self, texts: List[str]) -> List[str]:
        return [self.preprocess(text) for text in texts]

    def preprocess(self, text: str) -> str:
        if type(text) == NoneType:
            text = str(text)

        text = text.lower()
        return text


class VoiceMooreTokenizer:
    def __init__(self, vocab_file=None):
        self.tokenizer = None
        self.text_preprocessor = VoiceMooreTextPreprocessor()
        if vocab_file is not None:
            self.tokenizer = Tokenizer.from_file(vocab_file)

    def preprocess_text(self, txt, lang):
        return self.text_preprocessor.preprocess(txt)

    def encode(self, txt, lang):
        lang = lang.split("-")[0]  # remove the region
        txt = self.preprocess_text(txt, lang)
        txt = f"[{lang}]{txt}"
        txt = txt.replace(" ", "[SPACE]")

        return self.tokenizer.encode(txt).ids

    def decode(self, seq):
        if isinstance(seq, torch.Tensor):
            seq = seq.cpu().numpy()
        txt = self.tokenizer.decode(seq, skip_special_tokens=False).replace(" ", "")
        txt = txt.replace("[SPACE]", " ")
        txt = txt.replace("[STOP]", "")
        txt = txt.replace("[UNK]", "")
        return txt

    def __len__(self):
        return self.tokenizer.get_vocab_size()

    def get_number_tokens(self):
        return max(self.tokenizer.get_vocab().values()) + 1


class MooreGPTTrainer(GPTTrainer):
    def __init__(self, config: Coqpit):
        super().__init__(config)

        # create the tokenizer with the target vocabulary
        self.xtts.tokenizer = VoiceMooreTokenizer(self.args.tokenizer_file)
        # init gpt encoder and hifigan decoder
        self.xtts.init_models()

    @staticmethod
    def init_from_config(config: "GPTTrainerConfig", samples: Union[List[List], List[Dict]] = None):
        """Initiate model from config

        Args:
            config (GPTTrainerConfig): Model config.
            samples (Union[List[List], List[Dict]]): Training samples to parse speaker ids for training.
                Defaults to None.
        """
        return MooreGPTTrainer(config)
