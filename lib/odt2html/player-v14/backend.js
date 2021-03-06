/* odt2html player backend
** Copyright 2014--2017, Trinity College Computing Center
**
** This file is part of Odt2html.
**
** Odt2html is free software: you can redistribute it and/or modify
** it under the terms of the GNU General Public License as published by
** the Free Software Foundation, either version 3 of the License, or
** (at your option) any later version.
**
** Odt2html is distributed in the hope that it will be useful,
** but WITHOUT ANY WARRANTY; without even the implied warranty of
** MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
** GNU General Public License for more details.
**
** You should have received a copy of the GNU General Public License
** along with Odt2html. If not, see <http://www.gnu.org/licenses/>.
*/

"use strict";

/* IE does not define console unless the debugger is active! */
if(!window.console) window.console = {};
if(!window.console.log) window.console.log = function () { };

/* Override this to actually receive data */
if(!window.analytics) window.analytics = function() {};

window.players = (function() {

	/* Where are our resource files? Get basedir from src element of our <script> tag. */
	var res_basedir = document.getElementById("player_backend").src.replace(/\/[^\/]*$/, "");
	console.log("res_basedir:", res_basedir);

	/* Load additional Javascript code and call a function when it is ready */
	function load_js(id, src, callback) {
		if(document.getElementById(id)) {
			callback();
		} else {
			var el = document.createElement("script");
			el.id = id;
			el.type = "text/javascript";
			el.src = src;
			el.onload = callback;
			document.head.appendChild(el);
		}
	}
	
	/* Convenience function for building HTML tags, inspired by LXML */
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
							else if(name === 'onclick')
								el.onclick = arg[name];
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

	/* Add the basedir from the params if the URL is not absolute */
	function qualify_url(params, url) {
		if(url.match(/^https?:/i))
			return url;
		else
			return (params['basedir'] + "/" + url).replace(/\/[^\/]*\/\.\.\//g,'/');
	}

	/* Set media session
	   https://developer.mozilla.org/en-US/docs/Web/API/Media_Session_API
	   https://developers.google.com/web/updates/2017/02/media-session
	*/
	function set_media_session(params) {
		if('mediaSession' in navigator) {
			if(params) {
				var metadata = {};
				if('title' in params)
					metadata['title'] = params['title'];
				if('artist' in params)
					metadata['artist'] = params['artist'];
				if('album' in params)
					metadata['album'] = params['album'];
				if('artwork' in params)
					metadata['artwork'] = params['artwork'];
				console.log("MediaSession:", metadata);
				navigator.mediaSession.metadata = new MediaMetadata(metadata);
			} else {
				console.log("MediaSession: cleared");
				navigator.mediaSession.metadata = null;
			}
		} else {
			console.log("MediaSession: not supported by browser");
		}
	}

	/*==================================================
	** Audio or Video Player Download Menu
	**================================================*/

	function DownloadMenu(container) {
		var this_this = this;

		/* Button which opens and closes the menu */
		this.toggle_button = E("img", {
			alt: "Download",
			type: "image/svg+xml",
			src: res_basedir + "/btn_download.svg",
			onclick: function(event) {
				if(this_this.menu.style.display === "none") {
					this_this.menu.style.display = "block";
				} else {
					this_this.hide();
				}
				event.stopPropagation();
			}
		});
		container.appendChild(this.toggle_button);

		/* The menu itself (empty for now) */
		this.menu = E("div");
		this.menu.className = "player_menu";
		this.menu.style.display = "none";
		this.toggle_button.style.visibility = "hidden";
		container.appendChild(this.menu);
	}

	DownloadMenu.prototype.set_options = function(options) {
		while(this.menu.firstChild)
			this.menu.removeChild(this.menu.firstChild);

		for(var i=0; i < options.length; i++) {
			var option = options[i];
			var a = E("a", {
				type: option['mimetype'],
				download: "",
				href: option['src']
				});
			var this_this = this;
			a.onclick = function() {
				this_this.hide();
				return true;
			};
			for(var i2=0; i2 < option['label'].length; i2++)
				a.appendChild(E("span", option['label'][i2]));
			this.menu.appendChild(a);
		}

		this.toggle_button.style.visibility = options.length > 0 ? null : "hidden";
	}

	DownloadMenu.prototype.hide = function() {
		this.menu.style.display = "none";
	}

	/*==================================================
	** Audio Player with Controls
	**================================================*/
	
	function AudioPlayer() {
		var this_this = this;
		this.closed = true;
		this.params = null;
		this.src = null;
		this.highlighter = null;

		/* Build Audio Player GUI */
		this.panel = E("div", {className: "audio_player"});
		this.play_button = E("img", {
			alt: "Play",
			type: "image/svg+xml",
			src: res_basedir + "/btn_play.svg",
			});
		this.currentTime = E("span", "--:--", {className:"p_gui_time"});
		this.timeline_marker = E("div", {className:"p_gui_timeline_marker"});
		this.timeline = E("span", {className:"p_gui_timeline"}, this.timeline_marker);
		this.duration = E("span", "--:--", {className:"p_gui_time"});
		this.panel.appendChild(
			E("span", {className: "p_gui"},
				E("span", this.play_button),
				this.currentTime,
				this.timeline,
				this.duration
				)
			);
		this.download_menu = new DownloadMenu(this.panel);
		this.panel.appendChild(E("img", {
			alt: "Close Player",
			type: "image/svg+xml",
			src: res_basedir + "/btn_close.svg",
			onclick: function() { this_this.close(); }
			}));

		/* Create the actual player and connect it to the GUI */
		this.audio_tag = E("audio");
		this.audio_tag.addEventListener("play", function() {
			analytics('Audio', this_this.params['page'], 'play', this_this.src, this_this.audio_tag.currentTime);
			this_this.play_button.src = res_basedir + '/btn_pause.svg';
			this_this.play_button.alt = 'Pause';
		}, true);
		this.audio_tag.addEventListener("pause", function() {
			if(this_this.src !== null)
				analytics('Audio', this_this.params['page'], 'pause', this_this.src, this_this.audio_tag.currentTime);
			this_this.play_button.src = res_basedir + '/btn_play.svg';
			this_this.play_button.alt = 'Play';
		}, true);
		this.audio_tag.addEventListener("ended", function() {
			analytics('Audio', this_this.params['page'], 'ended', this_this.src);
			this_this.play_button.src = res_basedir + '/btn_play.svg';
			this_this.play_button.alt = 'Play';
			this_this.audio_tag.currentTime = 0;
			this_this.currentTime.innerHTML = "--:--";
		}, true);
		this.audio_tag.addEventListener("canplaythrough", function() {
			console.log("duration:", this_this.audio_tag.duration);
			this_this.duration.innerHTML = this_this.format_time(this_this.audio_tag.duration);
		});
		this.audio_tag.addEventListener("timeupdate", function() {
			//console.log("timeupdate:", this_this.audio_tag.currentTime);
			this_this.timeline_marker.style.marginLeft = this_this.audio_tag.currentTime / this_this.audio_tag.duration * 100 + "%";
			this_this.currentTime.innerHTML = this_this.format_time(this_this.audio_tag.currentTime);
		});
		this.play_button.addEventListener("click", function() {
			console.log("Play/Pause button pressed");
			if(this_this.audio_tag.paused) {
				this_this.audio_tag.play();
			} else {
				this_this.audio_tag.pause();
			}
		});
		this.timeline.addEventListener("click", function(event) {
			var clickFraction = (event.pageX - this_this.timeline.offsetLeft) / this_this.timeline.offsetWidth;
			//console.log("clickFraction:", clickFraction);
			this_this.audio_tag.currentTime = this_this.audio_tag.duration * clickFraction;
		});
		function drag_handler(event) {
			var clickFraction = (event.pageX - this_this.timeline.offsetLeft) / this_this.timeline.offsetWidth;
			//console.log("clickFraction:", clickFraction);
			if(clickFraction >= 0.0 && clickFraction <= 1.0)
				this_this.audio_tag.currentTime = this_this.audio_tag.duration * clickFraction;
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

	}

	/* Set the URL for the audio player to play and start playing it */
	AudioPlayer.prototype.play = function(params) {
		console.log("AudioPlayer.play(" + JSON.stringify(params) + ")");
		this.params = params;

		/* Tell the browser what we are playing */
		set_media_session(params);

		/* Sort the downloadable sources from worst to best quality */
		var sources = params['audio'];
		sources.sort(function(a, b) {
			if(a['mimetype'] > b['mimetype'])		/* ogg before mp3 */
				return -1;
			else if(a['mimetype'] === b['mimetype'])
				return a['filesize'] - b['filesize'];
			else
				return 1;
		});

		/* Format the list of downloadable sources and put it in the download menu. */
		var mimetypes = {
			'audio/mpeg': 'MP3',
			'audio/ogg': 'OGG'
		};
		var src = null;
		var downloads = [];
		for(var i=0; i < sources.length; i++) {
			var source = sources[i];
			var download = {
				label: [
					mimetypes[source['mimetype']],
					'filesize' in source ? (source['filesize'] / 1048576).toFixed(1) + "MB" : ""
					],
				mimetype: source['mimetype'],
				src: qualify_url(params, source['src'])
				};
			downloads.push(download);

			/* Remember the best quality source that this browser can play. */
			if(src === null && this.audio_tag.canPlayType(source['mimetype']))
				src = qualify_url(params, source['src']);
		}
		this.download_menu.set_options(downloads);

		/* Is there a WebVTT metadata track which tells us which words to highlight when? */
		while(this.audio_tag.firstChild)
			this.audio_tag.removeChild(this.audio_tag.firstChild);
		if('vtt' in params && 'highlighter' in params) {
			var webvtt = E("track", {
				src: qualify_url(params, params['vtt']),
				kind: 'metadata',
				label: 'cues',
				default: 'default'
				});
			this.audio_tag.appendChild(webvtt);
			var highlighter = params['highlighter'];
			webvtt.addEventListener("cuechange", function(event) {
				var cues = this.track.activeCues;
				var cue = cues.length ? cues[0].id : null;
				console.log("cue:", cue);
				highlighter.highlight(cue);
			});
			this.audio_tag.textTracks[0].mode = 'showing';
		}

		/* If the player GUI is hidden, make it appear. */
		if(this.closed) {
			document.body.appendChild(this.panel);
			document.body.className = "with_audio";
			this.closed = false;
		}	

		/* Play */
		this.audio_tag.src = src;
		this.src = src;
		this.audio_tag.load();
		this.audio_tag.play();
	}
	
	AudioPlayer.prototype.close = function() {
		console.log("Close audio player");
		if(!this.closed) {
			analytics('Audio', this.params['page'], 'close', this.src, this.audio_tag.currentTime);
			this.audio_tag.pause();
			set_media_session(null);
			if("highlighter" in this.params)
				this.params['highlighter'].close();
			this.download_menu.hide();
			document.body.removeChild(this.panel);
			document.body.className = "";
			this.params = null;
			this.src = null;
			this.closed = true;
		}
	}
	
	AudioPlayer.prototype.format_time = function(seconds) {
		var minutes = Math.floor(seconds / 60);
		seconds = Math.floor(seconds % 60);
		return minutes + ":" + (seconds < 10 ? "0" : "") + seconds;
	}

	/*==================================================
	** Video Player with Controls
	**================================================*/
	
	function VideoPlayer() {
		this.closed = true;
		this.params = null;
		this.src = null;			/* for analytics */
		this.src_mimetype = null;
		var this_this = this;		/* for setting up event handlers */
		this.youtube_api_ready = false;

		/* Video window and titlebar */
		this.div = E("div", {className: "video_player"});
		this.titlebar = E("div", {className: "video_titlebar"});
		this.div.appendChild(this.titlebar);
		this.title = E("div", {className: "video_titlebar_text"});
		this.titlebar.appendChild(this.title);
		this.download_menu = new DownloadMenu(this.titlebar);
		this.titlebar.appendChild(E("img", {
			alt: "Close Player",
			className: "close_btn",
			type: "image/svg+xml",
			src: res_basedir + "/btn_close.svg",
			onclick: function() { this_this.close(); }
			}));

		/* Let the user drag the video player by its titlebar. */
		this.top_left_x = null;
		this.top_left_y = null;
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

		/* The regular player */
		this.video_tag = E("video", {
			controls: true,
			autoplay: true
			});
		this.video_tag.addEventListener("play", function() {
			analytics('Video', this_this.params['page'], 'play', this_this.src, this_this.video_tag.currentTime);
		}, true);
		this.video_tag.addEventListener("pause", function() {
			if(this_this.src !== null)
				analytics('Video', this_this.params['page'], 'pause', this_this.src, this_this.video_tag.currentTime);
		}, true);
		this.video_tag.addEventListener("ended", function() {
			analytics('Video', this_this.params['page'], 'ended', this_this.src);
			this_this.video_tag.currentTime = 0;
		}, true);

		/* This video player will later be inserted into this div which
		   will determine its aspect ratio. */
		this.video_sizer = E("div");
		this.div.appendChild(this.video_sizer);
	}

	/* Set the URL of the video files for the player to play.
	   If the extension is .mp4, then assume the file is available only
	   in MP4 format (as external files frequently are).
	   If the extension is .webm, assume it is also available as WebM.
	*/
	VideoPlayer.prototype.play = function(params) {
		console.log("VideoPlayer.play(" + JSON.stringify(params) + ")");
		this.params = params;
		this.src = null;
		this.src_mimetype = null;
		var load_id = null;
		var load_url = null;
		var load_callback = null;
		var player_tag = this.video_tag;

		/* Tell the browser what we are playing */
		set_media_session(params);

		/* Set the title in the titlebar */
		this.title.innerHTML = params['title'];

		var downloads = [];
		if('video' in params) {
			/* Sort the downloadable sources from worst to best quality */
			var sources = params['video'];
			sources.sort(function(a, b) {
				if(a['mimetype'] === b['mimetype'])
					return a['framesize'][1] - b['framesize'][1];
				else if(a['mimetype'] < b['mimetype'])		/* mp4 before webm */
					return -1;
				else
					return 1;
			});
	
			/* Set the aspect ratio of the player to match that of the first video source. (We assume they are all the same.) */
			this.video_sizer.className = "video_sizer_" + sources[0]['aspect_ratio'].replace(":","x");
	
			/* Format the list of downloadable sources and put it into the download menu. */
			var mimetypes = {
				'video/mp4': 'MP4',
				'video/webm': 'WebM'
			};
			var video_sizes = {
				180: '240p',			/* 320x240 cropped to 16:9 */
				270: '360p',			/* 480x360 cropped to 16:9 */
				360: '480p'				/* 640x480 cropped to 16:9 */
			};
			for(var i=0; i < sources.length; i++) {
				var source = sources[i];
				var download = {
					label: [
						mimetypes[source['mimetype']],
						(source['framesize'][1] in video_sizes) ? video_sizes[source['framesize'][1]] : (source['framesize'][1] + 'p'),
						'filesize' in source ? Math.round(source['filesize'] / 1048576) + "MB" : ""
						],
					mimetype: source['mimetype'],
					codecs: source['codecs'],
					framesize: source['framesize'],
					src: qualify_url(params, source['src'])
					};
				downloads.push(download);
			}
		}
		this.download_menu.set_options(downloads);

		/* VTT track (captions) */
		while(this.video_tag.firstChild)
			this.video_tag.removeChild(this.video_tag.firstChild);
		if('vtt' in params) {
			var webvtt = E("track", {
				src: qualify_url(params, params['vtt']),
				kind: 'captions',
				label: 'English Captions',
				srclang: 'en'
				});
			this.video_tag.appendChild(webvtt);
		}

		if('youtube' in params) {
			console.log("Selecting Youtube player");
			this.src = "https://www.youtube.com/embed/" + params['youtube'];
			load_id = "youtube_iframe_api";
			load_url = "https://www.youtube.com/iframe_api";
			this.video_sizer.className = "video_sizer_16x9";
			player_tag = E("iframe", {
				id: "youtube",
				enablejsapi: "1",
				allowfullscreen: "allowfullscreen",
				src: this.src + "?enablejsapi=1&amp;autoplay=1&amp;rel=0"
				});
			var this_this = this;
			var events_set_up = false;
			var setup_events = function() {
				if(!events_set_up) {
					var player = new YT.Player("youtube", { events: {
						'onStateChange': function(event) {
							console.log("onStateChange:", event);
							if(event.data == YT.PlayerState.PLAYING)
								analytics('Video', this_this.params['page'], 'play', this_this.src, player.getCurrentTime());
							else if(event.data == YT.PlayerState.PAUSED)
								analytics('Video', this_this.params['page'], 'pause', this_this.src, player.getCurrentTime());
							else if(event.data == YT.PlayerState.ENDED)
								analytics('Video', this_this.params['page'], 'ended', this_this.src);
						}
					}});
					events_set_up = true;
				}
			}
			window.onYouTubeIframeAPIReady = function() { this_this.youtube_api_ready=true; setup_events(); };
			load_callback = function() { if(this_this.youtube_api_ready) setup_events(); };
		} else if('dash' in params && 'MediaSource' in window && MediaSource.isTypeSupported('video/webm;codecs="vp9,opus"')) {
			console.log("Selected Shaka Player");
			this.src = qualify_url(params, params['dash']);
			load_id = "shaka.min.js";
			load_url = res_basedir + "/" + load_id;
			var video = this.video_tag;
			var this_this = this;
			load_callback = function() {
				console.log("Shaka Player ready");
				shaka.polyfill.installAll();
				var dash = new shaka.Player(video);
				console.log("Shaka Player will play " + this_this.src);
				dash.load(this_this.src);
			};
		} else if('hls' in params) {
			if('MediaSource' in window && MediaSource.isTypeSupported('video/mp4;codecs="avc1.640029,mp4a.40.5"')) {
				console.log("Selected HLS.js");	
				this.src = qualify_url(params, params['hls']);
				load_id = "hls.min.js";
				load_url = res_basedir + "/" + load_id;
				var this_this = this;
				load_callback = function() {
					console.log("HLS.js ready");
					var hls = new Hls({
						capLevelToPlayerSize: true,
						maxMaxBufferLength : 60
						});
					console.log("HLS.js will play " + this_this.src);
					hls.loadSource(this_this.src);
					hls.attachMedia(this_this.video_tag);
					hls.on(Hls.Events.MANIFEST_PARSED,function() { this_this.video_tag.play() });
				};
			} else if(navigator.userAgent.indexOf("(iP") !== -1) {
				console.log("Selected built-in HLS player");
				this.src = qualify_url(params, params['hls']);
				this.src_mimetype = 'application/vnd.apple.mpegurl';
			}
		}

		/* If a DASH of HLS source was not selected above, use the best
		   of the downloadable representations as the source. */
		if(this.src === null) {
			for(var i = (sources.length - 1); i >= 0; i--) {
				var source = sources[i];
				var type = source['mimetype'];
				if('codecs' in source)
					type += (';codecs="' + source['codecs'] + '"');
				if((source['framesize'][0] <= window.innerWidth || i === 0) && this.video_tag.canPlayType(type)) {
					this.src = qualify_url(params, source['src']);
					this.src_mimetype = source['mimetype'];
					break;
				}
			}
		}

		/* Insert the player tag */
		while(this.video_sizer.firstChild)
			this.video_sizer.removeChild(this.video_sizer.firstChild);
		this.video_sizer.appendChild(player_tag);

		/* We are about ready. Let the player appear! */
		if(this.closed) {
			document.body.appendChild(this.div);
			this.closed = false;
		}
	
		/* Set the initial window position */
		if(this.top_left_x === null) {
			this.top_left_x = (window.innerWidth / 2 - this.div.offsetWidth / 2);
			/* 55px is approximate height of top navigation bar */
			this.top_left_y = Math.max((window.innerHeight / 2 - this.div.offsetHeight / 2), 55);
			this.div.style.left = this.top_left_x + "px";
			this.div.style.top = this.top_left_y + "px"; 
		}

		/* Play */
		if(load_id !== null) {
			console.log("Loading player " + load_id);
			load_js(load_id, load_url, load_callback);
		} else {
			console.log("Basic player will play " + this.src);
			this.video_tag.src = this.src;
			if(this.src_mimetype !== null)
				this.video_tag.type = this.src_mimetype;
			this.video_tag.load();
			this.video_tag.play();
		}
	}

	VideoPlayer.prototype.close = function() {
		console.log("Close video player");
		if(!this.closed) {
			analytics('Video', this.params['page'], 'close', this.src, this.video_tag.currentTime);
			this.video_tag.pause();
			set_media_session(null);
			this.download_menu.hide();
			document.body.removeChild(this.div);
			this.params = null;
			this.src = null;
			this.src_mimetype = null;
			this.closed = true;
		}
	}

	/*==================================================
	** Functions called from frontend
	**================================================*/

	var audio_player = null;
	var video_player = null;

	return {
		/* Invoke forground audio player with GUI controls */
		play_audio: function(params) {
			if(video_player !== null)
				video_player.close();
			if(audio_player === null)
				audio_player = new AudioPlayer();
			audio_player.play(params);
		},

		/* Invoke forground video player with GUI controls */
		play_video: function(params) {
			if(audio_player !== null)
				audio_player.close();
			if(video_player === null)
				video_player = new VideoPlayer();
			video_player.play(params);
		},

		/* Jump to a particular word in the recording */
		wordclick: function(word_index) {
			var startTime = audio_player.audio_tag.textTracks[0].cues[word_index].startTime;
			console.log("text click:", word_index, startTime);
			audio_player.audio_tag.currentTime = startTime + 0.001;
		},

		/* Called from page click handler */
		hide_menus: function() {
			console.log("Page click, hide player menus.");
			if(audio_player)
				audio_player.download_menu.hide();
			if(video_player)
				video_player.download_menu.hide();
		}
	};

})();
