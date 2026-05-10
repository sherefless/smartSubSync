local mp = require "mp"
local msg = require "mp.msg"
local utils = require "mp.utils"
local options = require "mp.options"

local opts = {
    python = "python3",
    helper_path = "",
    auto_sync = true,
    apply_delay = true,
    window_count = 6,
    window_duration = 60,
    search_range = 120,
    coarse_step = 0.5,
    fine_step = 0.02,
    threshold = 0.5,
    min_speech_ms = 120,
    min_silence_ms = 180,
    min_overlap_percent = 45,
    min_improvement_percent = 8,
    auto_retry = true,
}

options.read_options(opts, "smartsubsync")
math.randomseed(os.time())

local last_sync_key = nil
local pending_timer = nil
local progress_timer = nil
local progress_path = nil
local running = false

local function script_dir()
    local path = debug.getinfo(1, "S").source
    if path:sub(1, 1) == "@" then
        path = path:sub(2)
    end
    return utils.split_path(path)
end

local function default_helper_path()
    if opts.helper_path ~= "" then
        return opts.helper_path
    end
    return utils.join_path(utils.join_path(script_dir(), ".."), "smartsubsync_cli.py")
end

local function is_absolute_path(path)
    if not path or path == "" then
        return false
    end
    if path:sub(1, 1) == "/" then
        return true
    end
    if path:match("^%a:[/\\]") then
        return true
    end
    return false
end

local function decode_uri_component(value)
    return (value:gsub("%%(%x%x)", function(hex)
        return string.char(tonumber(hex, 16))
    end))
end

local function file_uri_to_path(path)
    if not path or path == "" then
        return path
    end

    if path:sub(1, 7) == "file://" then
        local decoded = decode_uri_component(path:sub(8))
        if decoded:match("^/%a:") then
            return decoded:sub(2)
        end
        return decoded
    end

    if path:sub(1, 5) == "file:" then
        local decoded = decode_uri_component(path:sub(6))
        if decoded:match("^/%a:") then
            return decoded:sub(2)
        end
        return decoded
    end

    return path
end

local function absolutize_path(path)
    path = file_uri_to_path(path)
    if not path or path == "" or is_absolute_path(path) then
        return path
    end
    local working_directory = mp.get_property("working-directory")
    if not working_directory or working_directory == "" then
        return path
    end
    return utils.join_path(working_directory, path)
end

local function selected_external_subtitle()
    local tracks = mp.get_property_native("track-list", {})
    local sid = mp.get_property_native("sid")
    for _, track in ipairs(tracks) do
        if track.type == "sub" and track.selected then
            return track["external-filename"] or track["external_filename"] or track["filename"], track.id
        end
    end

    if sid == nil or sid == false then
        return nil, nil
    end

    for _, track in ipairs(tracks) do
        if track.type == "sub" and track.id == sid then
            return track["external-filename"] or track["external_filename"] or track["filename"], track.id
        end
    end

    return nil, nil
end

local function temp_progress_path()
    local temp_dir = os.getenv("TMPDIR") or os.getenv("TEMP") or os.getenv("TMP") or "/tmp"
    local name = string.format(
        "smartsubsync-progress-%d-%d.json",
        os.time(),
        math.random(100000, 999999)
    )
    return utils.join_path(temp_dir, name)
end

local function read_text_file(path)
    local file = io.open(path, "r")
    if not file then
        return nil
    end
    local content = file:read("*a")
    file:close()
    return content
end

local function show_progress()
    if not progress_path then
        return
    end

    local content = read_text_file(progress_path)
    if not content or content == "" then
        return
    end

    local payload = utils.parse_json(content)
    if not payload then
        return
    end

    local percent = tonumber(payload.percent) or 0
    local message = payload.message or "analyzing"
    local text = string.format("smartSubSync: %d%% - %s", percent, message)

    mp.osd_message(text, 1.2)
end

local function start_progress_polling(path)
    progress_path = path
    if progress_timer then
        progress_timer:kill()
    end
    progress_timer = mp.add_periodic_timer(0.7, show_progress)
end

local function stop_progress_polling()
    if progress_timer then
        progress_timer:kill()
        progress_timer = nil
    end
    if progress_path then
        os.remove(progress_path)
        progress_path = nil
    end
end

local function build_args(video_path, subtitle_path, progress_file)
    local args = {
        opts.python,
        default_helper_path(),
        "--json",
        "--progress-file", progress_file,
        "--window-count", tostring(opts.window_count),
        "--window-duration", tostring(opts.window_duration),
        "--search-range", tostring(opts.search_range),
        "--coarse-step", tostring(opts.coarse_step),
        "--fine-step", tostring(opts.fine_step),
        "--threshold", tostring(opts.threshold),
        "--min-speech-ms", tostring(opts.min_speech_ms),
        "--min-silence-ms", tostring(opts.min_silence_ms),
        "--min-overlap-percent", tostring(opts.min_overlap_percent),
        "--min-improvement-percent", tostring(opts.min_improvement_percent),
        video_path,
        subtitle_path,
    }
    if not opts.auto_retry then
        table.insert(args, 4, "--no-auto-retry")
    end
    return args
end

local function apply_result(result)
    if type(result) ~= "table" then
        mp.osd_message("smartSubSync: helper returned no result", 6)
        msg.error("Helper returned no result table")
        return
    end

    local payload = utils.parse_json(result.stdout or "")
    if not payload or not payload.offset_seconds then
        mp.osd_message("smartSubSync: invalid helper output", 4)
        msg.error("Invalid helper output: " .. (result.stdout or ""))
        if result.stderr and result.stderr ~= "" then
            msg.error("Helper stderr: " .. result.stderr)
        end
        return
    end

    local offset = tonumber(payload.offset_seconds)
    if not offset then
        mp.osd_message("smartSubSync: invalid offset", 4)
        msg.error("Invalid offset payload: " .. (result.stdout or ""))
        return
    end

    local overlap = tonumber(payload.best_overlap_percent) or 0
    local improvement = tonumber(payload.overlap_improvement_percent) or 0
    local elapsed = tonumber(payload.elapsed_seconds) or 0
    if payload.reliable == false then
        mp.osd_message(
            string.format(
                "smartSubSync: confidence too low, not applied (overlap %.2f%%, gain %.2f%%)",
                overlap,
                improvement
            ),
            8
        )
        msg.warn("Low confidence sync result: " .. (result.stdout or ""))
        return
    end

    if opts.apply_delay then
        mp.set_property_number("sub-delay", offset)
    end

    local retry_note = payload.retry_used and ", retry" or ""
    mp.osd_message(
        string.format(
            "smartSubSync: %+0.3fs, overlap %.2f%%%s, %.2fs",
            offset,
            overlap,
            retry_note,
            elapsed
        ),
        6
    )
end

local function run_sync()
    if running then
        return
    end

    local video_path = absolutize_path(mp.get_property("path"))
    local subtitle_path = absolutize_path(selected_external_subtitle())
    if not video_path or not subtitle_path then
        return
    end

    local key = video_path .. "\n" .. subtitle_path
    if key == last_sync_key then
        return
    end
    last_sync_key = key
    running = true

    local current_progress_path = temp_progress_path()
    start_progress_polling(current_progress_path)
    mp.osd_message("smartSubSync: analyzing subtitle sync...", 3)
    mp.command_native_async(
        {
            name = "subprocess",
            playback_only = false,
            capture_stdout = true,
            capture_stderr = true,
            args = build_args(video_path, subtitle_path, current_progress_path),
        },
        function(success, result, error)
            running = false
            stop_progress_polling()
            if type(success) == "table" and result == nil then
                result = success
                success = result.error == nil
                error = result.error
            end

            local status = result and result.status
            if not success or status ~= 0 then
                local detail = error
                    or (result and result.stderr)
                    or (result and result.error_string)
                    or "unknown error"
                local first_line = string.match(detail, "([^\r\n]+)") or detail
                mp.osd_message("smartSubSync failed: " .. first_line, 8)
                msg.error(detail)
                if result and result.stdout and result.stdout ~= "" then
                    msg.error("stdout: " .. result.stdout)
                end
                return
            end
            apply_result(result)
        end
    )
end

local function schedule_sync()
    if not opts.auto_sync then
        return
    end
    if pending_timer then
        pending_timer:kill()
    end
    pending_timer = mp.add_timeout(0.5, run_sync)
end

mp.observe_property("sid", "native", schedule_sync)
mp.observe_property("track-list", "native", schedule_sync)
mp.add_key_binding("ctrl+s", "smartsubsync-run", run_sync)
