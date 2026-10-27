#  Load the KDUA-Mobile dataset in R, with the traps already handled.
#
#      source("code/load.R")
#      d <- kdua_load(".")
#      str(d$sessions)
#      g <- kdua_sensors(d, d$sessions$session_id[1])
#
#  Requires readr; arrow is needed only for the sensor files. Install with
#      install.packages(c("readr", "arrow"))
#
#  The same three decisions as in load.py are made here, in writing:
#    * the analysis subset excludes guided_step 1, the familiarisation session,
#      and the single session recorded outside the guided sequence;
#    * the on-surface condition is selected on motion_active_fraction, which was
#      measured, never on hold_style, which is what the participant was asked;
#    * sensor frames are read on demand, because all of them are 389 MB.

STILL  <- 0.10   # motion_active_fraction below this is "on a surface"
MOVING <- 0.20   # at or above this is "in the hand"

kdua_load <- function(root = ".", analysis_only = TRUE) {
  if (!requireNamespace("readr", quietly = TRUE)) {
    stop("install.packages('readr')")
  }
  data <- file.path(root, "data")

  sessions     <- readr::read_csv(file.path(data, "sessions.csv"),
                                  show_col_types = FALSE)
  participants <- readr::read_csv(file.path(data, "participants.csv"),
                                  show_col_types = FALSE)
  devices      <- readr::read_csv(file.path(data, "devices.csv"),
                                  show_col_types = FALSE)
  key_events   <- readr::read_csv(file.path(data, "key_events.csv.gz"),
                                  show_col_types = FALSE)

  if (analysis_only) {
    keep <- !is.na(sessions$guided_step) &
            sessions$guided_step >= 2 & sessions$guided_step <= 6
    sessions   <- sessions[keep, ]
    key_events <- key_events[key_events$session_id %in% sessions$session_id, ]
  }

  structure(list(root = root, sessions = sessions,
                 participants = participants, devices = devices,
                 key_events = key_events), class = "kdua")
}

#  The sensor frame of one session. Three sessions have no file at all: their
#  stream never started, so select on sensor_sample_count > 0 first.
kdua_sensors <- function(d, session_id) {
  pq <- file.path(d$root, "data", "sensors", paste0(session_id, ".parquet"))
  gz <- file.path(d$root, "data", "sensors", paste0(session_id, ".csv.gz"))
  if (file.exists(pq)) {
    if (!requireNamespace("arrow", quietly = TRUE)) {
      stop("install.packages('arrow') to read the Parquet sensor files")
    }
    return(as.data.frame(arrow::read_parquet(pq)))
  }
  if (file.exists(gz)) {
    return(as.data.frame(readr::read_csv(gz, show_col_types = FALSE)))
  }
  stop(sprintf("no sensor file for %s", session_id))
}

kdua_on_surface <- function(d) {
  d$sessions[!is.na(d$sessions$motion_active_fraction) &
             d$sessions$motion_active_fraction < STILL, ]
}

kdua_in_hand <- function(d) {
  d$sessions[!is.na(d$sessions$motion_active_fraction) &
             d$sessions$motion_active_fraction >= MOVING, ]
}

#  Sessions where which key was pressed is published.
kdua_key_identity <- function(d) {
  d$sessions[d$sessions$privacy_mode == "KEY_ID", ]
}

#  The conservative subset for impostor analysis: it cannot contain two
#  unlinked records of the same person. See docs/known_issues.md 2.6.
kdua_own_device <- function(d) {
  d$participants[d$participants$own_device == "own", ]
}

#  Sessions with the participant and device columns attached.
kdua_join <- function(d) {
  x <- merge(d$sessions, d$participants,
             by = c("participant_id", "device_id"), all.x = TRUE)
  merge(x, d$devices, by = "device_id", all.x = TRUE)
}
