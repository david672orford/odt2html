/* odt2html player backend */

"use strict";

/* IE does not define console unless the debugger is active! */
if(!window.console) window.console = {};
if(!window.console.log) window.console.log = function () { };

/* Override this to actually receive data */
if(!window.analytics) window.analytics = function() {};

window.players = (function() {

	/* Where are the SVG files? */
	var basedir = "/lib/odt2html";

	/* Convenience function inspired by LXML */
	function E(name) {
		var el = document.createElement(name);
		for(var i=1; i<arguments.length; i++) {
			var arg = arguments[i];
			switch(typeof(arg)) {
				case 'string':
					el.appendChild(document.createTextNode(arg));
					break;
				case 'object':
					if('nodeType' in arg) {
						el.appendChild(arg);
					} else {
						for(var name in arg) {
							if(name === 'className')
								el.setAttribute('class', arg[name]);
							else
								el.setAttribute(name, arg[name]);
						}
					}
					break;
				default:
					throw "Unhandled case: " + arg;
					break;
			}
		}
		return el;
	}
	
	/*==================================================
	** Audio Player Without Controls
	**================================================*/
	
	function AudioPlayer() {
		this.audio_tag = E("audio");
	
		this.source_ogg = E("source", {type:"audio/ogg"});
		this.audio_tag.appendChild(this.source_ogg);
	
		this.source_mp3 = E("source", {type:"audio/mpeg"});
		this.audio_tag.appendChild(this.source_mp3);
	
		this.webvtt = null;
	}
	
	/* Set the URL of the audio files for the player to play.
	   If the extension is .mp3, then assume the file is available only
	   in MP3 format (as external files frequently are).
	   If the extesion is .ogg, assume it is also available as MP3.
	*/
	AudioPlayer.prototype.play_url = function(url) {
		if(url.substr(-4) === ".mp3") {			/* MP3 only */
			this.source_ogg.removeAttribute("src");
			this.source_mp3.src = url;
		} else if(url.indexOf(".ogg#") != -1) {		/* fragment */
			this.source_ogg.src = url;
			this.source_mp3.src = url.replace(".ogg#",".mp3#");
		} else {
			this.source_ogg.src = url;
			this.source_mp3.src = url.replace(".ogg", ".mp3");
		}
		if(this.webvtt !== null) {
			this.video_tag.removeChild(this.webvtt);
			this.webvtt = null;
		}
		this.audio_tag.load();
		this.audio_tag.play();
	}

	/*==================================================
	** AudioPlayer GUI controls added
	**================================================*/
	
	function GuiAudioPlayer() {
		var this_this = this;
		this.closed = false;
		this.url = null;
		this.highlighter = null;

		this.div = E("div", {className: "audio_player"});

		this.menu = new PlayerMenu([
			"Download Audio as OGG",
			"Download Audio as MP3"
			]);
		this.div.appendChild(this.menu.menu_btn);
		this.div.appendChild(this.menu.menu);

		/* Player (without GUI) */
		this.player = new AudioPlayer();

		/* Player GUI */
		this.play_button = E("img", {type:"image/svg+xml", src:basedir + "/btn_play.svg", alt:"Play"});
		this.currentTime = E("span", "--:--", {className:"p_gui_time"});
		this.timeline_marker = E("div", {className:"p_gui_timeline_marker"});
		this.timeline = E("span", {className:"p_gui_timeline"}, this.timeline_marker);
		this.duration = E("span", "--:--", {className:"p_gui_time"});
		this.div.appendChild(
			E("span", {className: "p_gui"},
				E("span", this.play_button),
				this.currentTime,
				this.timeline,
				this.duration
				)
			);
		this.player.audio_tag.addEventListener("ended", function() {
			analytics('Audio', 'ended', this_this.url);
			this_this.play_button.src = basedir + '/btn_play.svg';
			this_this.play_button.alt = 'Play';
			this_this.currentTime.innerHTML = "--:--";
		}, true);
		this.player.audio_tag.addEventListener("pause", function() {
			analytics('Audio', 'paused', this_this.url, this_this.player.audio_tag.currentTime);
			this_this.play_button.src = basedir + '/btn_play.svg';
			this_this.play_button.alt = 'Play';
		}, true);
		this.player.audio_tag.addEventListener("play", function() {
			analytics('Audio', 'resumed', this_this.url, this_this.player.audio_tag.currentTime);
			this_this.play_button.src = basedir + '/btn_pause.svg';
			this_this.play_button.alt = 'Pause';
		}, true);
		this.player.audio_tag.addEventListener("canplaythrough", function() {
			console.log("duration:", this_this.player.audio_tag.duration);
			this_this.duration.innerHTML = this_this.format_time(this_this.player.audio_tag.duration);
		});
		this.player.audio_tag.addEventListener("timeupdate", function() {
			//console.log("timeupdate:", this_this.player.audio_tag.currentTime);
			this_this.timeline_marker.style.marginLeft = this_this.player.audio_tag.currentTime / this_this.player.audio_tag.duration * 100 + "%";
			this_this.currentTime.innerHTML = this_this.format_time(this_this.player.audio_tag.currentTime);
		});
		this.play_button.addEventListener("click", function() {
			console.log("Play/Pause button pressed");
			if(this_this.player.audio_tag.paused) {
				this_this.player.audio_tag.play();
			} else {
				this_this.player.audio_tag.pause();
			}
		});
		this.timeline.addEventListener("click", function(event) {
			var clickFraction = (event.pageX - this_this.timeline.offsetLeft) / this_this.timeline.offsetWidth;
			//console.log("clickFraction:", clickFraction);
			this_this.player.audio_tag.currentTime = this_this.player.audio_tag.duration * clickFraction;
		});
		function drag_handler(event) {
			var clickFraction = (event.pageX - this_this.timeline.offsetLeft) / this_this.timeline.offsetWidth;
			//console.log("clickFraction:", clickFraction);
			if(clickFraction >= 0.0 && clickFraction <= 1.0)
				this_this.player.audio_tag.currentTime = this_this.player.audio_tag.duration * clickFraction;
			event.preventDefault();
		}
		function drag_done_handler(event) {
			window.removeEventListener("mousemove", drag_handler);
			window.removeEventListener("mouseup", drag_done_handler);
		}
		this.timeline_marker.addEventListener("mousedown", function(event) {
			window.addEventListener("mousemove", drag_handler);
			window.addEventListener("mouseup", drag_done_handler);
		});

		var close_btn = E("img", { src: basedir + "/btn_close.svg" });
		close_btn.onclick = function() { this_this.close(); };
		this.div.appendChild(close_btn);

		document.body.appendChild(this.div);
		document.body.className = "with_audio";
	}
	
	/* Set the URL for the GUI player to play */
	GuiAudioPlayer.prototype.play_url = function(url, title, highlight_track, highlighter) {
		console.log("AudioPlayer.play_url(", url, title, highlight_track, highlighter, ")");
		this.url = url;
		this.highlighter = highlighter;

		analytics('Audio', 'play', this.url);

		/* Start playing */
		this.player.play_url(url);
	
		/* Is there a WebVTT metadata track which tells us which words to highlight when? */
		if(highlight_track !== null) {
	
			/* Add the cue track to the <audio> tag */
			this.webvtt = E("track", {src: highlight_track, kind: 'metadata', label: 'cues', default:'default'});
			this.player.audio_tag.appendChild(this.webvtt);
			var this_this = this;
			this.webvtt.addEventListener("cuechange", function(event) {
				var cues = this.track.activeCues;
				var cue = cues.length ? cues[0].id : null;
				console.log("cue:", cue);
				this_this.highlighter.highlight(cue);
			});
			this.player.audio_tag.textTracks[0].mode = 'showing';
		}
	
		/* Set links in download menu */
		if(this.player.source_ogg.hasAttribute("src")) {
			this.menu.options[0].href = this.player.source_ogg.src;
		} else {
			this.menu.options[0].removeAttribute("href");
		}
		this.menu.options[1].href = this.player.source_mp3.src;
	
	}
	
	GuiAudioPlayer.prototype.close = function() {
		console.log("Close audio player");
		if(!this.closed) {
			analytics('Audio', 'closed', this.url, this.player.audio_tag.currentTime);
			this.player.audio_tag.pause();
			if(this.highlighter)
				this.highlighter.close();
			document.body.removeChild(this.div);
			document.body.className = "";
			this.closed = true;
		}
	}
	
	GuiAudioPlayer.prototype.format_time = function(seconds) {
		var minutes = Math.floor(seconds / 60);
		seconds = Math.floor(seconds % 60);
		return minutes + ":" + (seconds < 10 ? "0" : "") + seconds;
	}

	/*==================================================
	** Video Player with Controls
	**================================================*/
	
	function VideoPlayer() {
		var this_this = this;
		this.closed = false;
		this.url = null;
	
		this.div = E("div", {className: "video_player"});
	
		this.titlebar = E("div", {className: "video_titlebar"});
		this.div.appendChild(this.titlebar);

		this.menu = new PlayerMenu([								/* player menu */
			"Download Video as Webm",
			"Download Video as MP4"
			]);
		this.titlebar.appendChild(this.menu.menu_btn);
		this.titlebar.appendChild(this.menu.menu);
	
		this.title = E("div", {className: "video_titlebar_text"});
		this.titlebar.appendChild(this.title);
	
		this.video_tag = E("video", {controls: true});				/* video player, empty for now */
		this.source_webm = E("source", {type: "video/webm"});
		this.video_tag.appendChild(this.source_webm);
		this.source_mp4 = E("source", {type: "video/mp4"});
		this.video_tag.appendChild(this.source_mp4);
		this.webvtt = null;
		this.video_tag.addEventListener("ended", function() {
			analytics('Video', 'ended', this_this.url);
		}, true);
		this.video_tag.addEventListener("pause", function() {
			analytics('Video', 'paused', this_this.url, this_this.video_tag.currentTime);
		}, true);
		this.video_tag.addEventListener("play", function() {
			analytics('Video', 'resumed', this_this.url, this_this.video_tag.currentTime);
		}, true);
		this.div.appendChild(E("div", {className: 'video_sizer'}, this.video_tag));
	
		var close_btn = E("img", { className: "close_btn", src: basedir + "/btn_close.svg" });
		close_btn.onclick = function() { this_this.close(); };
		this.titlebar.appendChild(close_btn);
	
		document.body.appendChild(this.div);
	
		/* Set the initial position */
		this.top_left_x = (window.innerWidth / 2 - this.div.offsetWidth / 2);
		this.top_left_y = (window.innerHeight / 2 - this.div.offsetHeight / 2);
		this.div.style.left =   this.top_left_x + "px";
		this.div.style.top = this.top_left_y + "px"; 
		
		/* Let the user drag the video player by its titlebar. */
		this.prev_x = null;
		this.prev_y = null;

		this.mousemove_handler = function(event) {
			//console.log("drag: coords: (" + event.clientX + ", " + event.clientY + ")");
			this_this.top_left_x += (event.clientX - this_this.prev_x);
			this_this.top_left_y += (event.clientY - this_this.prev_y);
			this_this.div.style.left = this_this.top_left_x + "px";
			this_this.div.style.top = this_this.top_left_y + "px"; 
			this_this.prev_x = event.clientX;
			this_this.prev_y = event.clientY;
		};

		this.drag_end_handler = function() {
			this_this.title.removeEventListener('mousemove', this_this.mousemove_handler, false);
			this_this.title.className = this_this.title.className.replace(" video_grabbing","");
		};

		this.title.addEventListener('mousedown', function(event) {
			console.log("drag: start: (" + event.clientX + ", " + event.clientY + ")");
			this_this.prev_x = event.clientX;
			this_this.prev_y = event.clientY;
			this_this.title.addEventListener('mousemove', this_this.mousemove_handler, false);
			this_this.title.className = this_this.title.className + " video_grabbing";
			event.preventDefault();
		}, false);
		this.title.addEventListener('mouseup', function(event) {
			console.log("drag: mouseup");
			this_this.drag_end_handler();
		}, false);
		this.title.addEventListener('mouseout', function(event) {
			console.log("drag: mouseout");
			this_this.drag_end_handler();
		}, false);
	}
	
	VideoPlayer.prototype.page_click = function(event) {
		//console.log("page_click:", event.target.id);
		this.menu.hide();
	}
	
	/* Set the URL of the video files for the player to play.
	   If the extension is .mp4, then assume the file is available only
	   in MP4 format (as external files frequently are).
	   If the extension is .webm, assume it is also available as MP4.
	*/
	VideoPlayer.prototype.play_url = function(url, title, captions) {
		console.log("VideoPlayer.play_url(", url, title, captions, ")");
		console.log("Window size:", window.innerWidth, window.innerHeight);

		/* Should we substitute a reduced-resolution version? */
		if(window.innerWidth <= 320)
			url = url.replace("%20640x480.", "%20320x240.");
		else if(window.innerWidth <= 480)
			url = url.replace("%20640x480.", "%20480x360.");

		this.url = url;
		this.title.innerHTML = title;

		analytics('Video', 'play', url);

		if(url.substr(-4) === ".mp4") {
			this.source_webm.removeAttribute("src");
			this.source_mp4.src =  url;
			this.menu.options[0].removeAttribute("href");
		} else {
			this.source_webm.src = url;
			this.source_mp4.src =  url.replace(".webm",".mp4");
			this.menu.options[0].href =  this.source_webm.src;
		}
		if(this.webvtt !== null) {
			this.video_tag.removeChild(this.webvtt);
			this.webvtt = null;
		}
		if(captions) {
			this.webvtt = E("track", {src: captions, kind: 'captions', label: 'English'});
			this.video_tag.appendChild(this.webvtt);
		}
		this.menu.options[1].href =  this.source_mp4.src;
		this.video_tag.load();
		this.video_tag.play();
	}

	VideoPlayer.prototype.close = function() {
		console.log("Close video player");
		if(!this.closed) {
			analytics('Video', 'closed', this.url, this.video_tag.currentTime);
			document.body.removeChild(this.div);
			this.closed = true;
		}
	}

	/*==================================================
	** Audio or Video Player menu
	**================================================*/

	function PlayerMenu(option_labels) {
		var this_this = this;

		/* Button which opens and closes the menu */
		this.menu_btn = E("img");
		this.menu_btn.src = basedir + "/btn_menu.svg";

		/* Click on the menu button toggles its visibility */
		this.menu_btn.onclick = function(event) {
			if(this_this.menu.style.display === "none") {
				this_this.menu.style.display = "block";
			} else {
				this_this.hide();
			}
			event.stopPropagation();
		};

		/* The menu itself */
		this.menu = E("div");
		this.menu.className = "player_menu";
		this.menu.style.display = "none";

		/* Add the menu entries */
		this.options = [];
		for(var i=0; i < option_labels.length; i++) {
			var option = E("a");
			option.appendChild(document.createTextNode(option_labels[i]));
			option.onclick = function() {
				this_this.menu.style.display = "none";
				return true;
			}
			option.download = "";
			this.menu.appendChild(option);
			this.options[i] = option;
		}
	}

	PlayerMenu.prototype.hide = function() {
		this.menu.style.display = "none";
	}

	/*==================================================
	** Functions called from page
	**================================================*/

	var bg_player = null;
	var audio_player = null;
	var video_player = null;

	return {
		/* Invoke background audio player */
		bgplay: function(url) {
			console.log('bgplay("' + url + '")');
			if(bg_player === null) {
				bg_player = new AudioPlayer();
			}
			bg_player.play_url(url, null);
			analytics('TD Sound', 'play', url);
		},

		/* Invoke forground audio player with GUI controls */
		play_audio: function(url, title, highlight_track, highlighter) {
			console.log('play_audio("' + url + '")');
			if(video_player !== null) {
				video_player.close();
			}
			if(audio_player === null || audio_player.closed) {
				audio_player = new GuiAudioPlayer();
			}
			audio_player.play_url(url, title, highlight_track, highlighter);
		},

		/* Invoke forground video player with GUI controls */
		play_video: function(url, title, captions) {
			console.log('play_video("' + url + '")');
			if(audio_player !== null) {
				audio_player.close();
			}
			if(video_player === null || video_player.closed) {
				video_player = new VideoPlayer();
			}
			video_player.play_url(url, title, captions);
		},

		wordclick: function(word_index) {
			var startTime = audio_player.player.audio_tag.textTracks[0].cues[word_index].startTime;
			console.log("text click:", word_index, startTime);
			audio_player.player.audio_tag.currentTime = startTime + 0.001;
		},

		hide_menus: function() {
			if(audio_player)
				audio_player.menu.hide();
			if(video_player)
				video_player.menu.hide();
		}
	};

})();
