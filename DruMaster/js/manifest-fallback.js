"use strict";

// The drum-source manifest is tiny and versioned with the app. Keep an embedded copy so
// a transient GitHub Pages/cache failure for the JSON file can never block the START button.
//
// app.js still contains a legacy "songs/nanairo/chart.mid" bootstrap URL. Since the
// persistent asset cache is installed before app.js, that literal URL can otherwise be
// satisfied from nanairo's old unversioned cache before song-manager gets a chance to
// remap it. Route that legacy bootstrap request to the selected song's current, versioned
// MIDI URL here, after the cache layer is installed and before app.js runs. This applies
// to nanairo itself as well as every other song.
(function(){
  const embeddedDrumManifest={
    sourceVelocity:100,
    wav:{
      pathPrefix:"assets/drumsound-",
      parts:22,
      digits:3,
      bytes:17243836,
      sha256:"a06e1cd8fe4741b28e665c7827a8d44d3f6aeacdd3968b0da121df8ad1790317",
      sourceSampleRate:44100,
      channels:2,
      bitsPerSample:16
    },
    midi:{
      path:"assets/drumsound.mid",
      bytes:6366,
      sha256:"6fe934d11bf77704d51686ad520dab601f6cf7f46d32d3cb69086c1dc678d5a3"
    }
  };

  const nativeFetch=window.fetch.bind(window);
  const rawUrl=input=>typeof input==="string"?input:(input&&input.url)||"";
  const isLegacyNanairoMidi=url=>/(?:^|\/)songs\/nanairo\/chart\.mid(?:[?#].*)?$/.test(String(url||""));

  window.fetch=async function(input,init){
    const url=rawUrl(input);
    const current=globalThis.DruMasterSongs?.current;

    // Always replace app.js's hard-coded bootstrap URL with the current metadata URL.
    // Even nanairo must go through current.midi so a new ?v= value invalidates the
    // persistent MIDI cache after publishing a replacement chart.
    if(current?.midi&&isLegacyNanairoMidi(url)){
      const requested=String(url||"");
      const currentUrl=String(current.midi||"");
      if(requested!==currentUrl)return nativeFetch(currentUrl,init);
    }

    if(/(?:^|\/)assets\/drumsound-manifest\.json(?:[?#].*)?$/.test(url)){
      // Do not depend on a separate Pages request for this static metadata.
      return new Response(JSON.stringify(embeddedDrumManifest),{
        status:200,
        headers:{"Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store"}
      });
    }
    return nativeFetch(input,init);
  };
})();