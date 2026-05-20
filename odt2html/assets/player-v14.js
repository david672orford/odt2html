/* odt2html player frontend */

"use strict";

/* Loader */
window.addEventListener('DOMContentLoaded', function () {
	var res_basedir = "/lib/odt2html/player-v14";
	var el;

	/* Load the backend if it is not loaded already. If this page is
	   in an iframe, the backend will be loaded into the parent. */
	if(!parent.document.getElementById("player_backend")) {

		el = parent.document.createElement("link");
		el.rel = "stylesheet";
		el.type = "text/css";
		el.href = res_basedir + "/backend.min.css";
		parent.document.head.appendChild(el);

		el = parent.document.createElement("script");
		el.id = "player_backend";
		el.type = "text/javascript";
		el.src = res_basedir + "/backend.min.js";
		parent.document.head.appendChild(el);
	}

	/* If any item in the documents media playist uses the highlighter, load it. */
	for(var i = 0; i < playlist.length; i++) {
		if('player_id' in playlist[i]) {
			el = document.createElement("script");
			el.type = "text/javascript";
			el.src = res_basedir + "/highlighter.min.js";
			document.head.appendChild(el);
			break;
		}
	}

}, false);

function play(index) {
	console.log("play(" + index + ")");
	var params = playlist[index];

	/* Prepend the directory of this page to the basedir given in the manifest */
	if('basedir' in params && params['basedir'][0] !== '/') {
		console.log("basedir:", params['basedir']);
		params['basedir'] = window.location.pathname.replace(/\/[^\/]*$/, "") + "/" + params['basedir'];
		console.log("basedir after:", params['basedir']);
	}

	/* Take part of page title before the colon as the album name. */
	params['album'] = document.title.split(":")[0];

	/* Send the path of this page's URL so that it can be sent in the analytics pings. */
	params['page'] = window.location.pathname;

	if('video' in params || 'youtube' in params) {
		parent.players.play_video(params);
	} else {
		if('player_id' in params)
			params['highlighter'] = new Highlighter(params['player_id'], document.body);
		parent.players.play_audio(params);
	}
}

