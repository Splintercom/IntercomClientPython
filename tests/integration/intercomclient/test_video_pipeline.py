from intercomclient.video_pipeline import VideoPipeline


class TestVideoPipeline:
    def setup_method(self):
        self.pipeline = VideoPipeline()

    # def test_init_camera(self):
    #     capture = self.pipeline.init_camera(source=0)
    #     capture.release()
    #     assert not capture.isOpened()

    # def test_init_writer(self):
    #     with tempfile.NamedTemporaryFile(suffix=".avi", delete=False) as tmp:
    #         output_file_path = tmp.name
    #         writer = self.pipeline.init_writer(0, output_file_path=output_file_path)
    #     assert writer.isOpened()

    # def test_capture_frame(self):
    #     capture = self.pipeline.init_camera(source=0)
    #     frame = self.pipeline.capture_frame()
    #     capture.release()
    #     assert frame is not None
    #     assert not capture.isOpened()

    def test_record_segment(self):
        capture = self.pipeline.init_camera(source=0)
        self.pipeline.capture = capture
        self.pipeline.record_segment(segment_number=1, max_frames=10)
