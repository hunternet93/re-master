var levels = ['player', 'supporter', 'moderator', 'operator', 'administrator', 'developer', 'creator'];
var user;
var key;

function handleLogin(data, status) {
    $('#login-error').empty();
    $.mobile.loading('hide');
    if (typeof data.key !== 'undefined') {
        key = data.key;
        $.cookie('key', key);
    }
    
    if (typeof data.user !== 'undefined') {
        user = data.user;
        $('.username').text(user.username);
        $('.userlevel').text(levels[user.level]);
        $(':mobile-pagecontainer').pagecontainer('change', '#main');
    }
    
    if (typeof data.error !== 'undefined') {
        if (data.error == 'login incorrect') {
            $('#login-error').append('<p>Incorrect username or password.</p>');
        }
        $(':mobile-pagecontainer').pagecontainer('change', '#login');
    }
}

function doLogin() {
    $('#login-error').empty();
    if ($('#login-username').val().length < 1) {
        $('#login-error').append('<p>A username is required.</p>');
        return;
    }
    if ($('#login-password').val().length < 1) {
        $('#login-error').append('<p>A password is required.</p>');
        return;
    }
    
    $.post(
        '/user/login', {
            username: $('#login-username').val(),
            password: $('#login-password').val(),
        }, 
        handleLogin
    );
    
    $.mobile.loading('show', {text: 'logging in...', theme: 'b', textVisible: true});
}

function doLogout() {
    $.post('/user/logout', {key: key});
    $('#login-error').html('<p>You have been logged out</p>');
    $(':mobile-pagecontainer').pagecontainer('change', '#login');
}

function handleRegister (data, status) {
    $('#register-error').empty();
    $.mobile.loading('hide');

    if (data.success) {
        $(':mobile-pagecontainer').pagecontainer('change', '#register-complete-dialog');
    }
    
    else if (typeof data.error !== 'undefined') {
        $('#register-error').append('Something went wrong, even though no register errors are defined yet!');
    }
}

function doRegister() {
    $('#register-error').empty();
    if ($('#register-username').val().length < 1) {
        $('#register-error').append('<p>A username is required.</p>');
        return;
    }
    if ($('#register-password').val().length < 1) {
        $('#register-error').append('<p>A password is required.</p>');
        return;
    }
    if ($('#register-email').val().length < 1) {
        $('#register-error').append('<p>An email address is required.</p>');
        return;
    }
    
    $.post(
        '/user/register', {
            username: $('#register-username').val(),
            password: $('#register-password').val(),
            email: $('#register-email').val()
        },
        handleRegister
    );
    
    $.mobile.loading('show', {text: 'creating account...', theme: 'b', textVisible: true});
}

$(document).ready(function () {
    if (typeof $.cookie('key') !== 'undefined') {
        key = $.cookie('key');
        $.mobile.loading('show', {text: 'loading...', theme: 'b', textVisible: true});
        $.get('/user', {key: key}, handleLogin);
    }
        
    else {
        $(':mobile-pagecontainer').pagecontainer('change', '#login');
    }
});
