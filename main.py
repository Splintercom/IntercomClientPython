from intercomclient.video_pipeline import VideoPipeline
from intercomclient.config import Config

if __name__ == "__main__":
    pipeline = VideoPipeline(config=Config)
    pipeline.record_segment()