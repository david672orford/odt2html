/* odt2html player frontend */

"use strict";

/* Loader */
window.addEventListener('DOMContentLoaded', function () {
	var basedir = "/lib/odt2html/player-v10";
	var el;

	/* Load the backend if it is not loaded already. If this page is
	   in an iframe, the backend will be loaded into the parent. */
	if(!parent.document.getElementById("player_backend")) {

		el = parent.document.createElement("link");
		el.rel = "stylesheet";
		el.type = "text/css";
		el.href = basedir + "/backend.css";
		parent.document.head.appendChild(el);

		el = parent.document.createElement("script");
		el.id = "player_backend";
		el.type = "text/javascript";
		el.src = basedir + "/backend.js";
		parent.document.head.appendChild(el);
	}

	/* If any item in the documents media playist uses the highlighter, load it. */
	for(var i = 0; i < playlist.length; i++) {
		if('player_id' in playlist[i]) {
			el = document.createElement("script");
			el.type = "text/javascript";
			el.src = basedir + "/highlighter.js";
			document.head.appendChild(el);
			break;
		}
	}

}, false);

function play(index) {
	console.log("play(" + index + ")");
	var params = playlist[index];
	if('video' in params) {
		parent.players.play_video(params);
	} else {
		if('player_id' in params)
			params['highlighter'] = new Highlighter(params['player_id'], document.body);
		parent.players.play_audio(params);
	}
}

