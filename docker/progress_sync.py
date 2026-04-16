#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import time

start_ts = time.time()

import faulthandler
import logging
import signal
import sys
import threading
import uuid

from common import settings
from common.config_utils import show_configs
from common.log_utils import init_root_logger
from common.versions import get_ragflow_version

from api.db.db_models import init_database_tables as init_web_db
from api.db.services.document_service import DocumentService
from rag.utils.redis_conn import RedisDistributedLock

stop_event = threading.Event()


def update_progress():
    lock_value = str(uuid.uuid4())
    redis_lock = RedisDistributedLock("update_progress", lock_value=lock_value, timeout=60)
    logging.info(f"update_progress lock_value: {lock_value}")
    while not stop_event.is_set():
        try:
            if redis_lock.acquire():
                DocumentService.update_progress()
                redis_lock.release()
        except Exception:
            logging.exception("update_progress exception")
        finally:
            try:
                redis_lock.release()
            except Exception:
                logging.exception("update_progress exception")
            stop_event.wait(6)


def signal_handler(sig, frame):
    logging.info("Received interrupt signal, shutting down...")
    stop_event.set()
    stop_event.wait(1)
    sys.exit(0)


if __name__ == "__main__":
    faulthandler.enable()
    init_root_logger("progress_sync")
    logging.info(f"""
        ____   ___    ______ ______ __
       / __ \ /   |  / ____// ____// /____  _      __
      / /_/ // /| | / / __ / /_   / // __ \| | /| / /
     / _, _// ___ |/ /_/ // __/  / // /_/ /| |/ |/ /
    /_/ |_|/_/  |_|\____//_/    /_/ \____/ |__/|__/
    """)
    logging.info(f"RAGFlow version: {get_ragflow_version()}")
    show_configs()
    settings.init_settings()
    init_web_db()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logging.info(f"Progress sync is ready after {time.time() - start_ts}s initialization.")
    update_progress()
